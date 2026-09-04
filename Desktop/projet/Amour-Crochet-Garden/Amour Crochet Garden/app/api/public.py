"""Public-facing routes: landing, products, events, feedback, cart, checkout."""

import json
import re
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import async_session_maker
from app.core.security import (
    check_checkout_rate_limit,
    check_rate_limit,
    generate_csrf_token,
    is_sumup_checkout_url,
    verify_csrf,
)
from app.core.templating import create_templates, render
from app.models import Event, EventType, Feedback, Product, ProductCategory, Setting

_MAX_NAME_LEN = 100
_MAX_EMAIL_LEN = 254
_MAX_MESSAGE_LEN = 2000
_EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

router = APIRouter()
BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = create_templates(BASE_DIR)
templates.env.globals["current_year"] = lambda: datetime.now().year


async def get_settings_dict() -> dict:
    async with async_session_maker() as session:
        result = await session.execute(select(Setting))
        rows = result.scalars().all()
        return {row.key: row.value for row in rows} if rows else {}


def _product_to_dict(p, category_name=None):
    stock = getattr(p, "stock_quantity", None)
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "price": p.price,
        "image_path": p.image_path,
        "available": p.available,
        "stock_quantity": stock,
        "in_stock": p.available and (stock is None or stock > 0),
        "category_name": category_name,
    }


def _format_event_dt(dt) -> str:
    """Show date; include time only when not midnight."""
    if not dt:
        return ""
    if getattr(dt, "hour", 0) == 0 and getattr(dt, "minute", 0) == 0:
        return dt.strftime("%d/%m/%Y")
    return dt.strftime("%d/%m/%Y - %H:%M")


def _event_to_dict(e, event_type_name=None):
    date_display = _format_event_dt(e.date)
    if e.date_end:
        date_display += " → " + _format_event_dt(e.date_end)
    return {
        "id": e.id,
        "title": e.title,
        "date_display": date_display,
        "date_iso": e.date.isoformat() if e.date else "",
        "location": e.location,
        "description": e.description[:150] + ("..." if len(e.description) > 150 else ""),
        "description_full": e.description,
        "event_type_name": event_type_name or "",
    }


def _parse_float_or_none(val: str | None) -> float | None:
    if val is None or not str(val).strip():
        return None
    try:
        return float(val)
    except ValueError:
        return None


def _parse_social_links(settings: dict) -> list:
    from app.core.security import is_safe_external_url

    links = []
    if settings.get("social_links"):
        try:
            raw = json.loads(settings["social_links"])
            if isinstance(raw, list):
                links = raw
        except (json.JSONDecodeError, TypeError):
            links = []
    if not links:
        if settings.get("instagram"):
            links.append({"name": "Instagram", "url": settings["instagram"]})
        if settings.get("tiktok"):
            links.append({"name": "TikTok", "url": settings["tiktok"]})
    safe = []
    for link in links:
        if not isinstance(link, dict):
            continue
        name = str(link.get("name") or "").strip()[:80]
        url = str(link.get("url") or "").strip()[:500]
        if name and url and is_safe_external_url(url):
            safe.append({"name": name, "url": url})
    return safe


async def _template_context(request: Request, **extra) -> dict:
    """Shared template context (settings + footer social links)."""
    settings = extra.pop("settings", None)
    if settings is None:
        settings = await get_settings_dict()
    cfg = get_settings()
    settings.setdefault("contact_email", cfg.contact_email)
    settings.setdefault("email", settings.get("email") or cfg.contact_email)
    settings["social_links_parsed"] = _parse_social_links(settings)
    ctx = {
        "request": request,
        "settings": settings,
        "footer_social": settings["social_links_parsed"],
    }
    ctx.update(extra)
    return ctx


# --- Pages légales / FAQ ---

_LEGAL_SLUGS = {
    "faq": "faq",
    "livraison": "livraison",
    "retours": "retours",
    "confidentialite": "confidentialite",
    "cookies": "cookies",
    "mentions-legales": "mentions-legales",
}


@router.get("/faq", response_class=HTMLResponse)
@router.get("/livraison", response_class=HTMLResponse)
@router.get("/retours", response_class=HTMLResponse)
@router.get("/confidentialite", response_class=HTMLResponse)
@router.get("/cookies", response_class=HTMLResponse)
@router.get("/mentions-legales", response_class=HTMLResponse)
async def legal_page(request: Request):
    from app.services.legal import get_legal_page

    slug = request.url.path.strip("/")
    page = get_legal_page(slug, get_settings().contact_email)
    if not page:
        return RedirectResponse(url="/", status_code=302)
    settings = await get_settings_dict()
    email = settings.get("contact_email") or get_settings().contact_email
    page = get_legal_page(slug, email) or page
    return render(
        templates,
        request,
        "legal.html",
        await _template_context(
            request,
            settings=settings,
            page_title=page["title"],
            page_subtitle=page["subtitle"],
            content=page["html"],
            active=page["active"],
        ),
    )


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    async with async_session_maker() as session:
        products_result = await session.execute(
            select(Product, ProductCategory.name)
            .outerjoin(ProductCategory, Product.category_id == ProductCategory.id)
            .where(Product.display == True)
            .order_by(Product.created_at.desc())
            .limit(5)
        )
        products = [_product_to_dict(p, cat_name) for p, cat_name in products_result.all()]

        events_result = await session.execute(
            select(Event, EventType.name)
            .outerjoin(EventType, Event.event_type_id == EventType.id)
            .where(Event.display == True)
            .order_by(Event.date.desc())
            .limit(5)
        )
        events = [_event_to_dict(e, et_name) for e, et_name in events_result.all()]

    settings = await get_settings_dict()
    cfg = get_settings()
    settings.setdefault("contact_email", cfg.contact_email)
    settings.setdefault("email", cfg.contact_email)
    settings["social_links_parsed"] = _parse_social_links(settings)

    csrf_token = generate_csrf_token()
    request.session["csrf_token"] = csrf_token

    return render(
        templates,
        request,
        "index.html",
        await _template_context(
            request,
            settings=settings,
            products=products,
            events=events,
            csrf_token=csrf_token,
        ),
    )


@router.get("/products", response_class=HTMLResponse)
async def products_page(
    request: Request,
    category: str | None = None,
    price_min: str | None = None,
    price_max: str | None = None,
    available_only: str | bool = False,
):
    p_min = _parse_float_or_none(price_min)
    p_max = _parse_float_or_none(price_max)
    avail = str(available_only).lower() in ("true", "1", "yes", "on") if available_only else False

    async with async_session_maker() as session:
        q = (
            select(Product, ProductCategory.name)
            .outerjoin(ProductCategory, Product.category_id == ProductCategory.id)
            .where(Product.display == True)
        )
        if category and str(category).strip():
            q = q.where(ProductCategory.name == category.strip())
        if p_min is not None:
            q = q.where(Product.price >= p_min)
        if p_max is not None:
            q = q.where(Product.price <= p_max)
        if avail:
            q = q.where(Product.available == True)
        q = q.order_by(Product.created_at.desc())

        result = await session.execute(q)
        products = [_product_to_dict(p, cat_name) for p, cat_name in result.all()]

        cat_result = await session.execute(
            select(ProductCategory.name).join(Product).where(Product.display == True).distinct()
        )
        categories = [r[0] for r in cat_result.all() if r[0]]

    settings = await get_settings_dict()
    csrf_token = generate_csrf_token()
    request.session["csrf_token"] = csrf_token
    return render(
        templates,
        request,
        "products.html",
        await _template_context(
            request,
            settings=settings,
            products=products,
            categories=categories,
            csrf_token=csrf_token,
            filters={
                "category": category and str(category).strip() or None,
                "price_min": p_min,
                "price_max": p_max,
                "available_only": avail,
            },
        ),
    )


@router.get("/events", response_class=HTMLResponse)
async def events_page(
    request: Request,
    event_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    location: str | None = None,
):
    async with async_session_maker() as session:
        q = (
            select(Event, EventType.name)
            .outerjoin(EventType, Event.event_type_id == EventType.id)
            .where(Event.display == True)
        )
        if event_type:
            q = q.where(EventType.name == event_type)
        if date_from:
            try:
                dt_from = datetime.fromisoformat(date_from.replace("Z", "+00:00"))
                q = q.where(Event.date >= dt_from)
            except ValueError:
                pass
        if date_to:
            try:
                dt_to = datetime.fromisoformat(date_to.replace("Z", "+00:00"))
                q = q.where(Event.date <= dt_to)
            except ValueError:
                pass
        if location:
            q = q.where(Event.location.ilike(f"%{location}%"))
        q = q.order_by(Event.date.desc())

        result = await session.execute(q)
        events = [_event_to_dict(e, et_name) for e, et_name in result.all()]

        type_result = await session.execute(
            select(EventType.name).join(Event).where(Event.display == True).distinct()
        )
        event_types = [r[0] for r in type_result.all() if r[0]]

    return render(
        templates,
        request,
        "events.html",
        await _template_context(
            request,
            events=events,
            event_types=event_types,
            filters={
                "event_type": event_type,
                "date_from": date_from,
                "date_to": date_to,
                "location": location,
            },
        ),
    )


@router.post("/feedback")
async def submit_feedback(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    message: str = Form(...),
    csrf_token: str | None = Form(None),
    website: str | None = Form(None),
):
    # Honeypot: si "website" est rempli, c'est un bot
    if website and website.strip():
        return RedirectResponse(url="/?feedback=sent#contact", status_code=302)

    # CSRF
    if not verify_csrf(request.session.get("csrf_token"), csrf_token):
        return RedirectResponse(url="/?feedback=error#contact", status_code=302)

    # Rate limiting
    ip = request.client.host if request.client else "unknown"
    if not check_rate_limit(ip):
        return RedirectResponse(url="/?feedback=rate_limit#contact", status_code=302)

    # Validation
    name = (name or "").strip()[: _MAX_NAME_LEN]
    email = (email or "").strip()[: _MAX_EMAIL_LEN]
    message = (message or "").strip()[: _MAX_MESSAGE_LEN]

    if not name or not message:
        return RedirectResponse(url="/?feedback=error#contact", status_code=302)

    if not _EMAIL_REGEX.match(email):
        return RedirectResponse(url="/?feedback=error#contact", status_code=302)

    async with async_session_maker() as session:
        session.add(Feedback(name=name, email=email, message=message))
        await session.commit()

    return RedirectResponse(url="/?feedback=sent#contact", status_code=302)


# --- Cart (session-based) ---


def _get_cart(request: Request) -> list[dict]:
    return request.session.get("cart") or []


def _set_cart(request: Request, cart: list[dict]) -> None:
    request.session["cart"] = cart


@router.post("/cart/add")
async def cart_add(
    request: Request,
    product_id: int = Form(...),
    qty: int = Form(1),
    csrf_token: str | None = Form(None),
):
    if not verify_csrf(request.session.get("csrf_token"), csrf_token):
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JSONResponse({"ok": False, "error": "session"}, status_code=403)
        return RedirectResponse(url="/products", status_code=302)
    if qty < 1:
        qty = 1
    if qty > 99:
        qty = 99

    async with async_session_maker() as session:
        result = await session.execute(
            select(Product, ProductCategory.name).outerjoin(
                ProductCategory, Product.category_id == ProductCategory.id
            ).where(Product.id == product_id, Product.display == True)
        )
        row = result.one_or_none()
        if not row:
            return RedirectResponse(url="/products", status_code=302)

        product, cat_name = row
        if not product.available:
            return RedirectResponse(url="/products", status_code=302)
        stock = getattr(product, "stock_quantity", None)
        if stock is not None and stock <= 0:
            return RedirectResponse(url="/products", status_code=302)

        product_snapshot = {
            "product_id": product.id,
            "name": product.name,
            "price": float(product.price),
            "image_path": product.image_path,
        }

    cart = _get_cart(request)
    current_qty = next((i["qty"] for i in cart if i["product_id"] == product_id), 0)
    total_qty = current_qty + qty
    if stock is not None and total_qty > stock:
        total_qty = stock
        qty = stock - current_qty
        if qty <= 0:
            return RedirectResponse(url="/cart", status_code=302)

    for item in cart:
        if item["product_id"] == product_id:
            item["qty"] = total_qty
            # Always refresh price/name from DB snapshot
            item["name"] = product_snapshot["name"]
            item["price"] = product_snapshot["price"]
            item["image_path"] = product_snapshot["image_path"]
            _set_cart(request, cart)
            break
    else:
        cart.append({
            **product_snapshot,
            "qty": total_qty if current_qty == 0 else qty,
        })
    _set_cart(request, cart)

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        count = sum(i["qty"] for i in cart)
        return JSONResponse({"ok": True, "count": count, "message": "Ajouté au panier"})

    return RedirectResponse(url="/cart", status_code=302)


@router.post("/cart/remove/{product_id}")
async def cart_remove(
    request: Request,
    product_id: int,
    csrf_token: str | None = Form(None),
):
    if not verify_csrf(request.session.get("csrf_token"), csrf_token):
        return RedirectResponse(url="/cart?error=session", status_code=302)
    cart = [i for i in _get_cart(request) if i["product_id"] != product_id]
    _set_cart(request, cart)
    return RedirectResponse(url="/cart", status_code=302)


@router.get("/cart", response_class=HTMLResponse)
async def cart_page(request: Request):
    from app.services.shipping import (
        FREE_SHIPPING_THRESHOLD,
        SHIPPING_FEE,
        order_totals,
    )

    settings = await get_settings_dict()
    cart = _get_cart(request)
    subtotal, shipping_fee, total = order_totals(cart) if cart else (0.0, 0.0, 0.0)
    csrf_token = generate_csrf_token()
    request.session["csrf_token"] = csrf_token
    return render(
        templates,
        request,
        "cart.html",
        await _template_context(
            request,
            settings=settings,
            cart=cart,
            subtotal=subtotal,
            shipping_fee=shipping_fee,
            total=total,
            shipping_fee_amount=SHIPPING_FEE,
            free_shipping_threshold=FREE_SHIPPING_THRESHOLD,
            csrf_token=csrf_token,
        ),
    )


@router.get("/cart/json")
async def cart_json(request: Request):
    from app.services.shipping import order_totals

    cart = _get_cart(request)
    subtotal, shipping_fee, total = order_totals(cart) if cart else (0.0, 0.0, 0.0)
    count = sum(item["qty"] for item in cart)
    return JSONResponse(
        {
            "cart": cart,
            "subtotal": subtotal,
            "shipping_fee": shipping_fee,
            "total": total,
            "count": count,
        }
    )


# --- Checkout (SumUp / mock) ---


@router.get("/checkout", response_class=HTMLResponse)
async def checkout_page(request: Request):
    from app.services.shipping import (
        FREE_SHIPPING_THRESHOLD,
        SHIPPING_FEE,
        order_totals,
    )

    cart = _get_cart(request)
    if not cart:
        return RedirectResponse(url="/cart", status_code=302)

    settings = await get_settings_dict()
    cfg = get_settings()
    subtotal, shipping_fee, total = order_totals(cart)
    csrf_token = generate_csrf_token()
    request.session["csrf_token"] = csrf_token
    return render(
        templates,
        request,
        "checkout.html",
        await _template_context(
            request,
            settings=settings,
            cart=cart,
            subtotal=subtotal,
            shipping_fee=shipping_fee,
            total=total,
            shipping_fee_amount=SHIPPING_FEE,
            free_shipping_threshold=FREE_SHIPPING_THRESHOLD,
            csrf_token=csrf_token,
            mock_payments=cfg.payments_mocked,
            mock_emails=cfg.emails_mocked,
            error=request.query_params.get("error"),
        ),
    )


@router.post("/checkout")
async def checkout_create(
    request: Request,
    csrf_token: str | None = Form(None),
    customer_first_name: str = Form(""),
    customer_last_name: str = Form(""),
    customer_email: str = Form(""),
    customer_phone: str = Form(""),
    shipping_address: str = Form(""),
    shipping_postal_code: str = Form(""),
    shipping_city: str = Form(""),
    shipping_country: str = Form("France"),
):
    if not verify_csrf(request.session.get("csrf_token"), csrf_token):
        return RedirectResponse(url="/checkout?error=session", status_code=302)

    ip = request.client.host if request.client else "unknown"
    if not check_checkout_rate_limit(ip):
        return RedirectResponse(url="/checkout?error=rate_limit", status_code=302)

    cart = _get_cart(request)
    if not cart:
        return RedirectResponse(url="/cart", status_code=302)

    first = (customer_first_name or "").strip()[:120]
    last = (customer_last_name or "").strip()[:120]
    email = (customer_email or "").strip()[:_MAX_EMAIL_LEN]
    phone = (customer_phone or "").strip()[:50]
    address = (shipping_address or "").strip()[:500]
    postal = (shipping_postal_code or "").strip()[:20]
    city = (shipping_city or "").strip()[:120]
    country = (shipping_country or "France").strip()[:80] or "France"

    if (
        not first
        or not last
        or not email
        or not _EMAIL_REGEX.match(email)
        or not address
        or not postal
        or not city
    ):
        return RedirectResponse(url="/checkout?error=contact", status_code=302)

    from app.services.orders import (
        attach_sumup_checkout,
        create_pending_order,
        rebuild_cart_from_db,
    )
    from app.services.shipping import order_totals
    from app.services.sumup_checkout import create_hosted_checkout, sumup_configured

    cfg = get_settings()
    mock_payments = cfg.payments_mocked

    if not mock_payments and not sumup_configured():
        return RedirectResponse(url="/checkout?error=payment_disabled", status_code=302)

    # Security: never trust session prices — rebuild from DB
    cart = await rebuild_cart_from_db(cart)
    if not cart:
        _set_cart(request, [])
        return RedirectResponse(url="/cart?error=unavailable", status_code=302)
    _set_cart(request, cart)

    subtotal, shipping_fee, total = order_totals(cart)
    if total <= 0:
        return RedirectResponse(url="/cart", status_code=302)

    order = await create_pending_order(
        customer_first_name=first,
        customer_last_name=last,
        customer_email=email,
        customer_phone=phone or None,
        shipping_address=address,
        shipping_postal_code=postal,
        shipping_city=city,
        shipping_country=country,
        cart=cart,
    )

    # Mode dev : simule un paiement réussi sans SumUp
    if mock_payments:
        await attach_sumup_checkout(order.id, f"mock_{order.reference}")
        request.session["pending_checkout_id"] = f"mock_{order.reference}"
        request.session["pending_checkout_reference"] = order.reference
        request.session["pending_order_id"] = order.id
        return RedirectResponse(
            url=f"/checkout/success?checkout_reference={order.reference}&mock=1",
            status_code=303,
        )

    base_url = str(request.base_url).rstrip("/")
    names = ", ".join(f'{i["name"]} ×{i["qty"]}' for i in cart[:5])
    if len(cart) > 5:
        names += f" (+{len(cart) - 5})"
    ship_label = "livraison offerte" if shipping_fee <= 0 else f"livraison {shipping_fee:.2f}€"
    description = f"Commande {order.reference} — {names} ({ship_label})"[:100]

    try:
        checkout = create_hosted_checkout(
            amount=total,
            description=description,
            redirect_url=f"{base_url}/checkout/success",
            checkout_reference=order.reference,
        )
        hosted_url = checkout.get("hosted_checkout_url") or ""
        if not is_sumup_checkout_url(hosted_url):
            return RedirectResponse(url="/checkout?error=payment_error", status_code=302)
        await attach_sumup_checkout(order.id, checkout.get("id"))
        request.session["pending_checkout_id"] = checkout.get("id")
        request.session["pending_checkout_reference"] = order.reference
        request.session["pending_order_id"] = order.id
        return RedirectResponse(url=hosted_url, status_code=303)
    except Exception:
        return RedirectResponse(url="/checkout?error=payment_error", status_code=302)


@router.get("/checkout/success", response_class=HTMLResponse)
async def checkout_success(
    request: Request,
    checkout_id: str | None = None,
    checkout_reference: str | None = None,
    id: str | None = None,
    mock: str | None = None,
):
    from app.services.orders import finalize_paid_order, get_order_by_reference
    from app.services.sumup_checkout import (
        find_checkout_by_reference,
        get_checkout,
        is_checkout_paid,
    )

    cfg = get_settings()
    pending_cid = request.session.get("pending_checkout_id")
    pending_ref = request.session.get("pending_checkout_reference")
    pending_order_id = request.session.get("pending_order_id")

    cid = checkout_id or id or pending_cid
    cref = checkout_reference or pending_ref

    # Clear pending markers after reading (one-shot)
    request.session.pop("pending_checkout_id", None)
    request.session.pop("pending_checkout_reference", None)
    request.session.pop("pending_order_id", None)

    order = await get_order_by_reference(cref)
    paid = False

    # Mock payment: only if mock mode ON, flag present, and order matches this session
    if (
        cfg.payments_mocked
        and mock == "1"
        and order is not None
        and pending_ref
        and order.reference == pending_ref
        and (pending_order_id is None or order.id == pending_order_id)
    ):
        paid = True
    else:
        checkout = get_checkout(cid) if cid and not str(cid).startswith("mock_") else None
        if not checkout and cref:
            checkout = find_checkout_by_reference(cref)
        paid = is_checkout_paid(checkout)
        if not order:
            order = await get_order_by_reference(
                (checkout or {}).get("checkout_reference")
            )

    if paid and order:
        order = await finalize_paid_order(order)
        _set_cart(request, [])

    settings = await get_settings_dict()
    return render(
        templates,
        request,
        "checkout_success.html",
        await _template_context(
            request,
            settings=settings,
            checkout_id=cid or (None if not order else order.sumup_checkout_id),
            payment_confirmed=paid,
            order_reference=order.reference if order else None,
            customer_email=order.customer_email if order and paid else None,
            email_sent=bool(order and order.customer_email_sent),
            mock_mode=cfg.payments_mocked or cfg.emails_mocked,
        ),
    )
