"""Admin panel routes."""

import json
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.database import async_session_maker
from app.core.logger import security_log
from app.core.security import (
    authenticate_admin,
    check_admin_login_rate_limit,
    create_session_token,
    ensure_admin_csrf,
    generate_csrf_token,
    get_admin_session,
    record_admin_login_failure,
    verify_csrf,
)
from app.core.templating import create_templates, render
from app.models import (
    Event,
    EventType,
    Feedback,
    Order,
    OrderItem,
    PageView,
    Product,
    ProductCategory,
    ReferralLink,
    ReferralVisit,
    Setting,
)

router = APIRouter()
BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = create_templates(BASE_DIR)
templates.env.globals["current_year"] = lambda: __import__("datetime").datetime.now().year


def _render_admin(request: Request, name: str, context: dict | None = None, *, status_code: int = 200):
    ctx = dict(context or {})
    ctx["csrf_token"] = ensure_admin_csrf(request)
    return render(templates, request, name, ctx, status_code=status_code)


def _login_page(request: Request, *, error: str | None = None, status_code: int = 200):
    csrf_token = generate_csrf_token()
    request.session["admin_csrf"] = csrf_token
    ctx = {"csrf_token": csrf_token}
    if error:
        ctx["error"] = error
    return render(templates, request, "admin/login.html", ctx, status_code=status_code)


@router.get("/", response_class=HTMLResponse)
async def admin_root(request: Request):
    return RedirectResponse(url="/admin/login", status_code=302)


@router.get("/order", response_class=HTMLResponse)
@router.get("/order/", response_class=HTMLResponse)
async def admin_order_alias(request: Request):
    """Compat: /admin/order → /admin/orders."""
    return RedirectResponse(url="/admin/orders", status_code=301)


@router.get("/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    if get_admin_session(request):
        return RedirectResponse(url="/admin/dashboard", status_code=302)
    return _login_page(request)


@router.post("/login")
async def admin_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    csrf_token: str | None = Form(None),
):
    ip = request.client.host if request.client else "unknown"
    if not verify_csrf(request.session.get("admin_csrf"), csrf_token):
        security_log("ADMIN_LOGIN_CSRF_FAIL", ip=ip, username=username[:20] if username else "")
        return _login_page(request, error="Session expirée. Réessayez.", status_code=403)
    if not check_admin_login_rate_limit(ip):
        security_log("ADMIN_LOGIN_RATE_LIMIT", ip=ip)
        return _login_page(
            request,
            error="Trop de tentatives. Réessayez dans 15 minutes.",
            status_code=429,
        )
    admin = await authenticate_admin(username, password)
    if not admin:
        record_admin_login_failure(ip)
        security_log("ADMIN_LOGIN_FAIL", ip=ip, username=username[:20] if username else "")
        return _login_page(request, error="Identifiants incorrects", status_code=401)
    security_log("ADMIN_LOGIN_OK", ip=ip, admin_id=str(admin.id))
    # Session fixation protection: clear then set fresh tokens
    request.session.clear()
    request.session["admin_session"] = create_session_token()
    request.session["admin_id"] = admin.id
    request.session["admin_csrf"] = generate_csrf_token()
    return RedirectResponse(url="/admin/dashboard", status_code=302)


@router.post("/logout")
async def admin_logout(request: Request, csrf_token: str | None = Form(None)):
    if not verify_csrf(request.session.get("admin_csrf"), csrf_token):
        return RedirectResponse(url="/admin/dashboard", status_code=302)
    admin_id = request.session.get("admin_id")
    ip = request.client.host if request.client else "unknown"
    security_log("ADMIN_LOGOUT", ip=ip, admin_id=str(admin_id) if admin_id else "")
    request.session.clear()
    return RedirectResponse(url="/admin/login", status_code=302)


@router.get("/logout")
async def admin_logout_get(request: Request):
    """GET logout kept for compatibility but clears session only if authenticated."""
    if get_admin_session(request):
        admin_id = request.session.get("admin_id")
        ip = request.client.host if request.client else "unknown"
        security_log("ADMIN_LOGOUT", ip=ip, admin_id=str(admin_id) if admin_id else "")
        request.session.clear()
    return RedirectResponse(url="/admin/login", status_code=302)


@router.get("/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    if not get_admin_session(request):
        return RedirectResponse(url="/admin/login", status_code=302)

    from datetime import timedelta

    now = datetime.utcnow()
    day0 = (now - timedelta(days=13)).replace(hour=0, minute=0, second=0, microsecond=0)
    since_30d = now - timedelta(days=30)

    async with async_session_maker() as session:
        products_count = await session.scalar(select(func.count(Product.id))) or 0
        events_count = await session.scalar(select(func.count(Event.id))) or 0
        orders_total = await session.scalar(select(func.count(Order.id))) or 0
        orders_paid = await session.scalar(
            select(func.count(Order.id)).where(Order.status == "paid")
        ) or 0
        orders_pending = await session.scalar(
            select(func.count(Order.id)).where(Order.status == "pending")
        ) or 0
        orders_failed = await session.scalar(
            select(func.count(Order.id)).where(Order.status == "failed")
        ) or 0
        revenue_total = await session.scalar(
            select(func.coalesce(func.sum(Order.total), 0.0)).where(Order.status == "paid")
        ) or 0.0
        revenue_30d = await session.scalar(
            select(func.coalesce(func.sum(Order.total), 0.0)).where(
                Order.status == "paid",
                Order.paid_at.is_not(None),
                Order.paid_at >= since_30d,
            )
        ) or 0.0
        # Fallback if paid_at missing on older rows
        if not revenue_30d:
            revenue_30d = await session.scalar(
                select(func.coalesce(func.sum(Order.total), 0.0)).where(
                    Order.status == "paid",
                    Order.created_at >= since_30d,
                )
            ) or 0.0
        aov = (float(revenue_total) / orders_paid) if orders_paid else 0.0
        feedback_unread = await session.scalar(
            select(func.count(Feedback.id)).where(Feedback.lu == False)
        ) or 0
        feedback_total = await session.scalar(select(func.count(Feedback.id))) or 0
        visitors_total = await session.scalar(
            select(func.count(func.distinct(PageView.ip_hash)))
        ) or 0
        page_views_total = await session.scalar(select(func.count(PageView.id))) or 0
        low_stock = await session.scalar(
            select(func.count(Product.id)).where(
                Product.stock_quantity.is_not(None),
                Product.stock_quantity <= 3,
                Product.display == True,
            )
        ) or 0

        # Last 14 days series (paid orders by created_at date)
        paid_orders = (
            await session.execute(
                select(Order).where(
                    Order.status == "paid",
                    Order.created_at >= day0,
                )
            )
        ).scalars().all()
        series_map: dict[str, dict] = {}
        for i in range(14):
            d = (day0 + timedelta(days=i)).date()
            key = d.isoformat()
            series_map[key] = {"date": key, "label": d.strftime("%d/%m"), "orders": 0, "revenue": 0.0}
        for order in paid_orders:
            if not order.created_at:
                continue
            key = order.created_at.date().isoformat()
            if key in series_map:
                series_map[key]["orders"] += 1
                series_map[key]["revenue"] += float(order.total or 0)
        chart_series = list(series_map.values())

        # Top products from paid order items
        top_rows = (
            await session.execute(
                select(
                    OrderItem.product_name,
                    func.sum(OrderItem.quantity).label("qty"),
                    func.sum(OrderItem.unit_price * OrderItem.quantity).label("rev"),
                )
                .join(Order, Order.id == OrderItem.order_id)
                .where(Order.status == "paid")
                .group_by(OrderItem.product_name)
                .order_by(func.sum(OrderItem.quantity).desc())
                .limit(5)
            )
        ).all()
        top_products = [
            {
                "name": r[0],
                "quantity": int(r[1] or 0),
                "revenue": float(r[2] or 0),
            }
            for r in top_rows
        ]

        # Views last 14 days
        views = (
            await session.execute(select(PageView).where(PageView.created_at >= day0))
        ).scalars().all()
        views_map = {k: 0 for k in series_map}
        for v in views:
            if not v.created_at:
                continue
            key = v.created_at.date().isoformat()
            if key in views_map:
                views_map[key] += 1
        for row in chart_series:
            row["views"] = views_map.get(row["date"], 0)

        referral_stats_result = await session.execute(
            select(ReferralLink.name, func.count(ReferralVisit.id))
            .join(ReferralVisit, ReferralLink.id == ReferralVisit.referral_id)
            .group_by(ReferralLink.id, ReferralLink.name)
            .order_by(func.count(ReferralVisit.id).desc())
        )
        referral_stats = [{"name": r[0], "visits": r[1]} for r in referral_stats_result.all()]

        recent_orders = (
            await session.execute(
                select(Order).order_by(Order.created_at.desc()).limit(5)
            )
        ).scalars().all()
        recent = [
            {
                "id": o.id,
                "reference": o.reference,
                "status": o.status,
                "total": float(o.total or 0),
                "customer": (
                    f"{(o.customer_first_name or '').strip()} {(o.customer_last_name or '').strip()}".strip()
                    or o.customer_name
                ),
                "date": o.created_at.strftime("%d/%m %H:%M") if o.created_at else "",
            }
            for o in recent_orders
        ]

    stats = {
        "products_count": products_count,
        "events_count": events_count,
        "orders_total": orders_total,
        "orders_paid": orders_paid,
        "orders_pending": orders_pending,
        "orders_failed": orders_failed,
        "revenue_total": float(revenue_total),
        "revenue_30d": float(revenue_30d),
        "aov": round(aov, 2),
        "feedback_unread": feedback_unread,
        "feedback_total": feedback_total,
        "visitors_total": visitors_total,
        "page_views_total": page_views_total,
        "low_stock": low_stock,
        "conversion_rate": round(
            (orders_paid / page_views_total * 100) if page_views_total else 0.0, 1
        ),
        "referral_stats": referral_stats,
        "chart_series": chart_series,
        "top_products": top_products,
        "recent_orders": recent,
        "status_breakdown": {
            "paid": orders_paid,
            "pending": orders_pending,
            "failed": orders_failed,
        },
    }
    return _render_admin(request, "admin/dashboard.html", {"stats": stats})


@router.get("/orders", response_class=HTMLResponse)
async def admin_orders(request: Request):
    if not get_admin_session(request):
        return RedirectResponse(url="/admin/login", status_code=302)

    status_labels = {
        "pending": "En attente",
        "paid": "Payée",
        "failed": "Échouée",
    }
    async with async_session_maker() as session:
        result = await session.execute(select(Order).order_by(Order.created_at.desc()))
        orders_db = list(result.scalars().all())
        orders = []
        for order in orders_db:
            items_result = await session.execute(
                select(OrderItem).where(OrderItem.order_id == order.id)
            )
            items = list(items_result.scalars().all())
            orders.append(
                {
                    "id": order.id,
                    "reference": order.reference,
                    "customer_name": order.customer_name,
                    "customer_first_name": order.customer_first_name,
                    "customer_last_name": order.customer_last_name,
                    "customer_email": order.customer_email,
                    "customer_phone": order.customer_phone,
                    "shipping_address": order.shipping_address,
                    "shipping_postal_code": order.shipping_postal_code,
                    "shipping_city": order.shipping_city,
                    "shipping_country": order.shipping_country,
                    "status": order.status,
                    "status_label": status_labels.get(order.status, order.status),
                    "subtotal": float(order.subtotal or 0),
                    "shipping_fee": float(order.shipping_fee or 0),
                    "total": order.total,
                    "customer_email_sent": order.customer_email_sent,
                    "admin_email_sent": order.admin_email_sent,
                    "created_at_display": (
                        order.created_at.strftime("%d/%m/%Y %H:%M") if order.created_at else ""
                    ),
                    "line_items": [
                        {
                            "product_name": i.product_name,
                            "quantity": i.quantity,
                            "unit_price": i.unit_price,
                        }
                        for i in items
                    ],
                }
            )

    return _render_admin(request, "admin/orders.html", {"orders": orders})


@router.get("/products", response_class=HTMLResponse)
async def admin_products(request: Request):
    if not get_admin_session(request):
        return RedirectResponse(url="/admin/login", status_code=302)
    async with async_session_maker() as session:
        result = await session.execute(
            select(Product, ProductCategory.name)
            .outerjoin(ProductCategory, Product.category_id == ProductCategory.id)
            .order_by(Product.created_at.desc())
        )
        rows = result.all()
        products_data = [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "price": p.price,
                "image_path": p.image_path,
                "category_name": cat_name or "",
                "available": p.available,
                "display": p.display,
                "stock_quantity": p.stock_quantity,
            }
            for p, cat_name in rows
        ]
        cat_result = await session.execute(select(ProductCategory).order_by(ProductCategory.name))
        categories = [{"id": c.id, "name": c.name} for c in cat_result.scalars().all()]
    return _render_admin(request, "admin/products.html", {
            "request": request,
            "products": products_data,
            "products_data": products_data,
            "categories": categories,
        },
    )


@router.get("/events", response_class=HTMLResponse)
async def admin_events(request: Request):
    if not get_admin_session(request):
        return RedirectResponse(url="/admin/login", status_code=302)
    async with async_session_maker() as session:
        result = await session.execute(
            select(Event, EventType.name)
            .outerjoin(EventType, Event.event_type_id == EventType.id)
            .order_by(Event.date.desc())
        )
        rows = result.all()

        def _fmt(dt):
            if not dt:
                return ""
            if dt.hour == 0 and dt.minute == 0:
                return dt.strftime("%d/%m/%Y")
            return dt.strftime("%d/%m/%Y %H:%M")

        events_data = [
            {
                "id": e.id,
                "title": e.title,
                "date": e.date.isoformat() if e.date else "",
                "date_end": e.date_end.isoformat() if e.date_end else "",
                "date_display": _fmt(e.date),
                "date_end_display": _fmt(e.date_end),
                "location": e.location,
                "event_type_name": et_name or "",
                "description": e.description,
                "display": e.display,
            }
            for e, et_name in rows
        ]
        et_result = await session.execute(select(EventType).order_by(EventType.name))
        event_types = [{"id": t.id, "name": t.name} for t in et_result.scalars().all()]
    return _render_admin(request, "admin/events.html", {
            "request": request,
            "events": events_data,
            "events_data": events_data,
            "event_types": event_types,
        },
    )


@router.get("/feedback", response_class=HTMLResponse)
async def admin_feedback(request: Request):
    if not get_admin_session(request):
        return RedirectResponse(url="/admin/login", status_code=302)
    async with async_session_maker() as session:
        result = await session.execute(select(Feedback).order_by(Feedback.created_at.desc()))
        feedback_list = [
            {
                "id": f.id,
                "name": f.name,
                "email": f.email,
                "message": f.message,
                "created_at_display": f.created_at.strftime("%d/%m/%Y %H:%M")
                if f.created_at
                else "",
                "lu": f.lu,
            }
            for f in result.scalars().all()
        ]
    return _render_admin(request, "admin/feedback.html", {"request": request, "feedback_list": feedback_list})


@router.get("/referrals", response_class=HTMLResponse)
async def admin_referrals(request: Request):
    if not get_admin_session(request):
        return RedirectResponse(url="/admin/login", status_code=302)
    return _render_admin(request, "admin/referrals.html", {"request": request})


@router.get("/settings", response_class=HTMLResponse)
async def admin_settings(request: Request):
    if not get_admin_session(request):
        return RedirectResponse(url="/admin/login", status_code=302)
    async with async_session_maker() as session:
        result = await session.execute(select(Setting))
        settings_dict = {row.key: row.value for row in result.scalars().all()}

    cfg = get_settings()
    settings_dict.setdefault("contact_email", cfg.contact_email)
    settings_dict.setdefault("intro_text", "")
    if not settings_dict.get("social_links"):
        links = []
        if settings_dict.get("instagram"):
            links.append({"name": "Instagram", "url": settings_dict["instagram"]})
        if settings_dict.get("tiktok"):
            links.append({"name": "TikTok", "url": settings_dict["tiktok"]})
        settings_dict["social_links"] = json.dumps(links) if links else "[]"
    try:
        settings_dict["social_links_parsed"] = json.loads(settings_dict["social_links"])
    except (json.JSONDecodeError, TypeError):
        settings_dict["social_links_parsed"] = []
    return _render_admin(request, "admin/settings.html", {
            "request": request,
            "settings": settings_dict,
            "emails_mocked": cfg.emails_mocked,
            "smtp_configured": bool(cfg.smtp_host and cfg.smtp_user),
        },
    )
