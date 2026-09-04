"""Order creation and payment finalization."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select

from app.core.database import async_session_maker
from app.core.logger import logger
from app.models import Order, OrderItem, Product
from app.services.email import (
    send_admin_order_notification,
    send_customer_order_confirmation,
)
from app.services.shipping import order_totals


def new_order_reference() -> str:
    return f"ACG-{uuid.uuid4().hex[:12].upper()}"


async def rebuild_cart_from_db(cart: list[dict]) -> list[dict] | None:
    """Re-fetch prices/stock from DB. Returns None if cart invalid/empty after rebuild."""
    if not cart:
        return None
    rebuilt: list[dict] = []
    async with async_session_maker() as session:
        for item in cart:
            try:
                product_id = int(item.get("product_id"))
                qty = int(item.get("qty") or 0)
            except (TypeError, ValueError):
                continue
            if qty < 1:
                continue
            product = await session.get(Product, product_id)
            if (
                not product
                or not product.display
                or not product.available
            ):
                continue
            stock = product.stock_quantity
            if stock is not None:
                if stock <= 0:
                    continue
                qty = min(qty, stock)
            rebuilt.append(
                {
                    "product_id": product.id,
                    "name": product.name,
                    "price": float(product.price),
                    "image_path": product.image_path,
                    "qty": qty,
                }
            )
    return rebuilt or None


async def create_pending_order(
    *,
    customer_first_name: str,
    customer_last_name: str,
    customer_email: str,
    customer_phone: str | None,
    shipping_address: str,
    shipping_postal_code: str,
    shipping_city: str,
    shipping_country: str,
    cart: list[dict],
) -> Order:
    subtotal, shipping_fee, total = order_totals(cart)
    first = customer_first_name.strip()[:120]
    last = customer_last_name.strip()[:120]
    full_name = f"{first} {last}".strip()[:255]
    order = Order(
        reference=new_order_reference(),
        customer_name=full_name,
        customer_first_name=first,
        customer_last_name=last,
        customer_email=customer_email.strip()[:255],
        customer_phone=(customer_phone or "").strip()[:50] or None,
        shipping_address=shipping_address.strip()[:500],
        shipping_postal_code=shipping_postal_code.strip()[:20],
        shipping_city=shipping_city.strip()[:120],
        shipping_country=(shipping_country or "France").strip()[:80],
        status="pending",
        subtotal=subtotal,
        shipping_fee=shipping_fee,
        total=total,
    )
    async with async_session_maker() as session:
        session.add(order)
        await session.flush()
        for item in cart:
            session.add(
                OrderItem(
                    order_id=order.id,
                    product_id=item.get("product_id"),
                    product_name=str(item.get("name") or "Article")[:255],
                    unit_price=float(item["price"]),
                    quantity=int(item["qty"]),
                )
            )
        await session.commit()
        await session.refresh(order)
        return order


async def attach_sumup_checkout(order_id: int, checkout_id: str | None) -> None:
    async with async_session_maker() as session:
        result = await session.execute(select(Order).where(Order.id == order_id))
        order = result.scalar_one_or_none()
        if not order:
            return
        order.sumup_checkout_id = checkout_id
        await session.commit()


async def get_order_by_reference(reference: str | None) -> Order | None:
    if not reference:
        return None
    async with async_session_maker() as session:
        result = await session.execute(select(Order).where(Order.reference == reference))
        return result.scalar_one_or_none()


async def get_order_with_items(order_id: int) -> tuple[Order | None, list[OrderItem]]:
    async with async_session_maker() as session:
        result = await session.execute(select(Order).where(Order.id == order_id))
        order = result.scalar_one_or_none()
        if not order:
            return None, []
        items_result = await session.execute(
            select(OrderItem).where(OrderItem.order_id == order.id)
        )
        return order, list(items_result.scalars().all())


def _format_address(order: Order) -> str:
    parts = [
        order.shipping_address or "",
        " ".join(
            p for p in [order.shipping_postal_code or "", order.shipping_city or ""] if p
        ).strip(),
        order.shipping_country or "",
    ]
    return "\n".join(p for p in parts if p)


async def finalize_paid_order(order: Order) -> Order:
    """Mark order paid, decrement stock, send emails once."""
    async with async_session_maker() as session:
        result = await session.execute(select(Order).where(Order.id == order.id))
        db_order = result.scalar_one_or_none()
        if not db_order:
            return order

        already_paid = db_order.status == "paid"
        if not already_paid:
            db_order.status = "paid"
            db_order.paid_at = datetime.utcnow()

            items_result = await session.execute(
                select(OrderItem).where(OrderItem.order_id == db_order.id)
            )
            items = list(items_result.scalars().all())
            for item in items:
                if not item.product_id:
                    continue
                product = await session.get(Product, item.product_id)
                if not product or product.stock_quantity is None:
                    continue
                # Atomic-ish stock check (SQLite single-writer)
                if product.stock_quantity < item.quantity:
                    logger.warning(
                        "Stock insuffisant pour produit %s (cmd %s)",
                        product.id,
                        db_order.reference,
                    )
                    product.stock_quantity = 0
                    product.available = False
                else:
                    product.stock_quantity -= item.quantity
                    if product.stock_quantity == 0:
                        product.available = False
        else:
            items_result = await session.execute(
                select(OrderItem).where(OrderItem.order_id == db_order.id)
            )
            items = list(items_result.scalars().all())

        item_dicts = [
            {
                "product_name": i.product_name,
                "unit_price": i.unit_price,
                "quantity": i.quantity,
            }
            for i in items
        ]
        address = _format_address(db_order)
        display_name = (
            f"{(db_order.customer_first_name or '').strip()} "
            f"{(db_order.customer_last_name or '').strip()}"
        ).strip() or db_order.customer_name

        if not db_order.customer_email_sent:
            ok = send_customer_order_confirmation(
                customer_name=display_name,
                customer_email=db_order.customer_email,
                reference=db_order.reference,
                subtotal=float(db_order.subtotal or 0),
                shipping_fee=float(db_order.shipping_fee or 0),
                total=db_order.total,
                shipping_address=address,
                items=item_dicts,
            )
            if ok:
                db_order.customer_email_sent = True
            else:
                logger.warning(
                    "Email client non envoyé pour commande %s", db_order.reference
                )

        if not db_order.admin_email_sent:
            ok = send_admin_order_notification(
                customer_name=display_name,
                customer_email=db_order.customer_email,
                customer_phone=db_order.customer_phone,
                reference=db_order.reference,
                subtotal=float(db_order.subtotal or 0),
                shipping_fee=float(db_order.shipping_fee or 0),
                total=db_order.total,
                shipping_address=address,
                items=item_dicts,
            )
            if ok:
                db_order.admin_email_sent = True
            else:
                logger.warning(
                    "Email admin non envoyé pour commande %s", db_order.reference
                )

        await session.commit()
        await session.refresh(db_order)
        return db_order
