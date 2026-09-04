"""REST API routes for admin operations."""

import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.database import async_session_maker
from app.core.logger import logger
from app.core.security import (
    extension_for_image_content,
    get_admin_session,
    is_safe_external_url,
    is_safe_image_path,
    validate_uploaded_image,
    verify_csrf,
)
from app.models import Event, EventType, Product, ProductCategory

router = APIRouter()
BASE_DIR = Path(__file__).resolve().parent.parent.parent
UPLOAD_DIR = BASE_DIR / "static" / "uploads"


def require_admin(request: Request) -> bool:
    if not get_admin_session(request):
        raise HTTPException(status_code=401, detail="Non authentifié")
    # CSRF on all state-changing admin API calls
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        token = request.headers.get("X-CSRF-Token")
        if not verify_csrf(request.session.get("admin_csrf"), token):
            raise HTTPException(status_code=403, detail="Jeton CSRF invalide")
    return True


def require_csrf(request: Request) -> bool:
    """Kept for explicit use; require_admin already enforces CSRF on writes."""
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return True
    token = request.headers.get("X-CSRF-Token")
    if not verify_csrf(request.session.get("admin_csrf"), token):
        raise HTTPException(status_code=403, detail="Jeton CSRF invalide")
    return True


def _ensure_upload_dir():
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _parse_bool_form(val) -> bool:
    if val is None:
        return True
    if isinstance(val, bool):
        return val
    return str(val).lower() not in ("false", "0", "no", "")


def _parse_int_or_none(val) -> int | None:
    if val is None or (isinstance(val, str) and not str(val).strip()):
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


async def _get_or_create_category(session, name: str | None) -> int | None:
    if not name or not name.strip():
        return None
    result = await session.execute(
        select(ProductCategory).where(ProductCategory.name == name.strip())
    )
    cat = result.scalar_one_or_none()
    if cat:
        return cat.id
    cat = ProductCategory(name=name.strip())
    session.add(cat)
    await session.flush()
    return cat.id


async def _get_or_create_event_type(session, name: str | None) -> int | None:
    if not name or not name.strip():
        return None
    result = await session.execute(select(EventType).where(EventType.name == name.strip()))
    et = result.scalar_one_or_none()
    if et:
        return et.id
    et = EventType(name=name.strip())
    session.add(et)
    await session.flush()
    return et.id


# --- Product Categories ---


@router.get("/categories")
async def list_categories(request: Request, _: bool = Depends(require_admin)):
    async with async_session_maker() as session:
        result = await session.execute(select(ProductCategory).order_by(ProductCategory.name))
        return [{"id": r.id, "name": r.name} for r in result.scalars().all()]


@router.post("/categories")
async def create_category(
    request: Request,
    name: str = Form(...),
    _: bool = Depends(require_admin),
):
    async with async_session_maker() as session:
        result = await session.execute(
            select(ProductCategory).where(ProductCategory.name == name.strip())
        )
        existing = result.scalar_one_or_none()
        if existing:
            return {"id": existing.id, "name": existing.name}
        cat = ProductCategory(name=name.strip())
        session.add(cat)
        await session.commit()
        await session.refresh(cat)
        return {"id": cat.id, "name": cat.name}


# --- Products ---


@router.get("/products")
async def list_products(request: Request, _: bool = Depends(require_admin)):
    async with async_session_maker() as session:
        result = await session.execute(
            select(Product, ProductCategory.name)
            .outerjoin(ProductCategory, Product.category_id == ProductCategory.id)
            .order_by(Product.created_at.desc())
        )
        return [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "price": p.price,
                "image_path": p.image_path,
                "category_id": p.category_id,
                "category_name": cat_name,
                "available": p.available,
                "display": p.display,
                "stock_quantity": p.stock_quantity,
            }
            for p, cat_name in result.all()
        ]


@router.post("/products")
async def create_product(
    request: Request,
    name: str = Form(...),
    description: str = Form(...),
    price: float = Form(...),
    category: str | None = Form(None),
    available: str | bool = Form("true"),
    display: str | bool = Form("true"),
    stock_quantity: int | None = Form(None),
    image: UploadFile | None = File(None),
    _: bool = Depends(require_admin),
):
    try:
        _ensure_upload_dir()
        settings = get_settings()
        max_bytes = settings.max_upload_size_mb * 1024 * 1024
        avail = _parse_bool_form(available)
        disp = _parse_bool_form(display)

        image_path = None
        if image and image.filename:
            content = await image.read()
            if len(content) > max_bytes:
                raise HTTPException(status_code=400, detail="Image trop volumineuse")
            ok, err = validate_uploaded_image(content, image.filename)
            if not ok:
                raise HTTPException(status_code=400, detail=err)
            ext = extension_for_image_content(content)
            filename = f"{uuid.uuid4()}{ext}"
            filepath = UPLOAD_DIR / filename
            filepath.write_bytes(content)
            image_path = f"uploads/{filename}"
            if not is_safe_image_path(image_path):
                raise HTTPException(status_code=400, detail="Chemin image invalide")

        async with async_session_maker() as session:
            category_id = await _get_or_create_category(session, category)
            product = Product(
                name=name,
                description=description,
                price=float(price),
                category_id=category_id,
                available=avail,
                display=disp,
                stock_quantity=_parse_int_or_none(stock_quantity),
                image_path=image_path,
            )
            session.add(product)
            await session.commit()
            await session.refresh(product)
            logger.info("POST /api/products -> created id=%s", product.id)
            return {"id": product.id, "name": product.name}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("create_product error: %s", e)
        raise HTTPException(status_code=500, detail="Erreur serveur")


@router.put("/products/{product_id}")
async def update_product(
    product_id: int,
    request: Request,
    name: str | None = Form(None),
    description: str | None = Form(None),
    price: float | None = Form(None),
    category: str | None = Form(None),
    available: str | None = Form(None),
    display: str | None = Form(None),
    stock_quantity: str | None = Form(None),
    image: UploadFile | None = File(None),
    _: bool = Depends(require_admin),
):
    try:
        _ensure_upload_dir()
        settings = get_settings()
        max_bytes = settings.max_upload_size_mb * 1024 * 1024

        async with async_session_maker() as session:
            result = await session.execute(select(Product).where(Product.id == product_id))
            product = result.scalar_one_or_none()
            if not product:
                raise HTTPException(status_code=404, detail="Produit non trouvé")

            if name is not None:
                product.name = name
            if description is not None:
                product.description = description
            if price is not None:
                product.price = float(price)
            if category is not None:
                product.category_id = await _get_or_create_category(session, category)
            if available is not None:
                product.available = _parse_bool_form(available)
            if display is not None:
                product.display = _parse_bool_form(display)
            if stock_quantity is not None:
                product.stock_quantity = _parse_int_or_none(stock_quantity)

            if image and image.filename:
                content = await image.read()
                if len(content) > max_bytes:
                    raise HTTPException(status_code=400, detail="Image trop volumineuse")
                ok, err = validate_uploaded_image(content, image.filename)
                if not ok:
                    raise HTTPException(status_code=400, detail=err)
                ext = extension_for_image_content(content)
                filename = f"{uuid.uuid4()}{ext}"
                filepath = UPLOAD_DIR / filename
                filepath.write_bytes(content)
                image_path = f"uploads/{filename}"
                if not is_safe_image_path(image_path):
                    raise HTTPException(status_code=400, detail="Chemin image invalide")
                product.image_path = image_path

            await session.commit()
            await session.refresh(product)
            logger.info("PUT /api/products/%s -> updated", product_id)
            return {"id": product.id, "name": product.name}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("update_product error: %s", e)
        raise HTTPException(status_code=500, detail="Erreur serveur")


@router.delete("/products/{product_id}")
async def delete_product(
    product_id: int,
    request: Request,
    _: bool = Depends(require_admin),
):
    async with async_session_maker() as session:
        result = await session.execute(select(Product).where(Product.id == product_id))
        product = result.scalar_one_or_none()
        if not product:
            raise HTTPException(status_code=404, detail="Produit non trouvé")
        await session.delete(product)
        await session.commit()
        logger.info("DELETE /api/products/%s -> deleted", product_id)
        return {"ok": True}


# --- Event Types ---


@router.get("/event-types")
async def list_event_types(request: Request, _: bool = Depends(require_admin)):
    async with async_session_maker() as session:
        result = await session.execute(select(EventType).order_by(EventType.name))
        return [{"id": r.id, "name": r.name} for r in result.scalars().all()]


@router.post("/event-types")
async def create_event_type(
    request: Request,
    name: str = Form(...),
    _: bool = Depends(require_admin),
):
    async with async_session_maker() as session:
        result = await session.execute(select(EventType).where(EventType.name == name.strip()))
        existing = result.scalar_one_or_none()
        if existing:
            return {"id": existing.id, "name": existing.name}
        et = EventType(name=name.strip())
        session.add(et)
        await session.commit()
        await session.refresh(et)
        return {"id": et.id, "name": et.name}


# --- Events ---


@router.get("/events")
async def list_events(request: Request, _: bool = Depends(require_admin)):
    async with async_session_maker() as session:
        result = await session.execute(
            select(Event, EventType.name)
            .outerjoin(EventType, Event.event_type_id == EventType.id)
            .order_by(Event.date.desc())
        )
        return [
            {
                "id": e.id,
                "title": e.title,
                "date": e.date.isoformat() if e.date else None,
                "date_end": e.date_end.isoformat() if e.date_end else None,
                "description": e.description,
                "location": e.location,
                "event_type_id": e.event_type_id,
                "event_type_name": et_name,
                "display": e.display,
            }
            for e, et_name in result.all()
        ]


def _parse_datetime(val: str | None) -> datetime | None:
    if not val or not str(val).strip():
        return None
    raw = str(val).strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        pass
    for fmt, length in (
        ("%Y-%m-%dT%H:%M:%S", 19),
        ("%Y-%m-%dT%H:%M", 16),
        ("%Y-%m-%d %H:%M", 16),
        ("%Y-%m-%d", 10),
    ):
        try:
            return datetime.strptime(raw[:length], fmt)
        except ValueError:
            continue
    return None


def _combine_date_time(date_val: str | None, time_val: str | None) -> str | None:
    """Build an ISO-like datetime string from separate date + optional time."""
    if not date_val or not str(date_val).strip():
        return None
    d = str(date_val).strip()[:10]
    t = (time_val or "").strip()
    if t:
        # HH:MM or HH:MM:SS
        parts = t.split(":")
        if len(parts) >= 2:
            return f"{d}T{parts[0].zfill(2)}:{parts[1].zfill(2)}"
    return d


@router.post("/events")
async def create_event(
    request: Request,
    title: str = Form(...),
    date: str = Form(...),
    time: str | None = Form(None),
    date_end: str | None = Form(None),
    time_end: str | None = Form(None),
    description: str = Form(...),
    location: str = Form(...),
    event_type: str | None = Form(None),
    display: bool = Form(True),
    _: bool = Depends(require_admin),
):
    dt = _parse_datetime(_combine_date_time(date, time) or date)
    if not dt:
        raise HTTPException(status_code=400, detail="Date invalide")
    end_raw = _combine_date_time(date_end, time_end) if date_end else None
    dt_end = _parse_datetime(end_raw) if end_raw else None

    async with async_session_maker() as session:
        event_type_id = await _get_or_create_event_type(session, event_type)
        event = Event(
            title=title,
            date=dt,
            date_end=dt_end,
            description=description,
            location=location,
            event_type_id=event_type_id,
            display=display,
        )
        session.add(event)
        await session.commit()
        await session.refresh(event)
        logger.info("POST /api/events -> created id=%s", event.id)
        return {"id": event.id, "title": event.title}


@router.put("/events/{event_id}")
async def update_event(
    event_id: int,
    request: Request,
    title: str | None = Form(None),
    date: str | None = Form(None),
    time: str | None = Form(None),
    date_end: str | None = Form(None),
    time_end: str | None = Form(None),
    description: str | None = Form(None),
    location: str | None = Form(None),
    event_type: str | None = Form(None),
    display: bool | None = Form(None),
    _: bool = Depends(require_admin),
):
    async with async_session_maker() as session:
        result = await session.execute(select(Event).where(Event.id == event_id))
        event = result.scalar_one_or_none()
        if not event:
            raise HTTPException(status_code=404, detail="Événement non trouvé")

        if title is not None:
            event.title = title
        if date is not None:
            parsed = _parse_datetime(_combine_date_time(date, time) or date)
            if parsed:
                event.date = parsed
        if date_end is not None:
            if not str(date_end).strip():
                event.date_end = None
            else:
                event.date_end = _parse_datetime(_combine_date_time(date_end, time_end))
        elif time_end is not None and event.date_end:
            # allow updating only end time if date_end already exists - skip, form always sends date_end
            pass
        if description is not None:
            event.description = description
        if location is not None:
            event.location = location
        if event_type is not None:
            event.event_type_id = await _get_or_create_event_type(session, event_type)
        if display is not None:
            event.display = display

        await session.commit()
        logger.info("PUT /api/events/%s -> updated", event_id)
        return {"id": event.id, "title": event.title}


@router.delete("/events/{event_id}")
async def delete_event(
    event_id: int,
    request: Request,
    _: bool = Depends(require_admin),
):
    async with async_session_maker() as session:
        result = await session.execute(select(Event).where(Event.id == event_id))
        event = result.scalar_one_or_none()
        if not event:
            raise HTTPException(status_code=404, detail="Événement non trouvé")
        await session.delete(event)
        await session.commit()
        logger.info("DELETE /api/events/%s -> deleted", event_id)
        return {"ok": True}


# --- Feedback ---


@router.get("/feedback")
async def list_feedback(request: Request, _: bool = Depends(require_admin)):
    from app.models import Feedback

    async with async_session_maker() as session:
        result = await session.execute(select(Feedback).order_by(Feedback.created_at.desc()))
        return [
            {
                "id": f.id,
                "name": f.name,
                "email": f.email,
                "message": f.message,
                "created_at": f.created_at.isoformat() if f.created_at else None,
                "lu": f.lu,
            }
            for f in result.scalars().all()
        ]


@router.delete("/feedback/{feedback_id}")
async def delete_feedback(
    feedback_id: int,
    request: Request,
    _: bool = Depends(require_admin),
):
    from app.models import Feedback

    async with async_session_maker() as session:
        result = await session.execute(select(Feedback).where(Feedback.id == feedback_id))
        fb = result.scalar_one_or_none()
        if not fb:
            raise HTTPException(status_code=404, detail="Feedback non trouvé")
        await session.delete(fb)
        await session.commit()
        logger.info("DELETE /api/feedback/%s -> deleted", feedback_id)
        return {"ok": True}


@router.patch("/feedback/{feedback_id}/read")
async def mark_feedback_read(
    feedback_id: int,
    request: Request,
    _: bool = Depends(require_admin),
):
    from app.models import Feedback

    async with async_session_maker() as session:
        result = await session.execute(select(Feedback).where(Feedback.id == feedback_id))
        fb = result.scalar_one_or_none()
        if not fb:
            raise HTTPException(status_code=404, detail="Feedback non trouvé")
        fb.lu = True
        await session.commit()
        logger.info("PATCH /api/feedback/%s/read -> marked read", feedback_id)
        return {"ok": True}


# --- Settings ---


@router.get("/settings")
async def get_settings_api(request: Request, _: bool = Depends(require_admin)):
    from app.models import Setting

    async with async_session_maker() as session:
        result = await session.execute(select(Setting))
        return {row.key: row.value for row in result.scalars().all()}


@router.post("/settings")
async def update_settings(
    request: Request,
    _: bool = Depends(require_admin),
):
    import json as _json

    from app.models import Setting

    data = await request.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Données invalides")

    # Sanitize social_links JSON (block javascript: URLs)
    if "social_links" in data and data["social_links"] is not None:
        try:
            raw_links = _json.loads(data["social_links"]) if isinstance(data["social_links"], str) else data["social_links"]
            clean = []
            if isinstance(raw_links, list):
                for link in raw_links:
                    if not isinstance(link, dict):
                        continue
                    name = str(link.get("name") or "").strip()[:80]
                    url = str(link.get("url") or "").strip()[:500]
                    if name and url and is_safe_external_url(url):
                        clean.append({"name": name, "url": url})
            data["social_links"] = _json.dumps(clean)
        except (_json.JSONDecodeError, TypeError):
            data["social_links"] = "[]"

    # Contact email: basic length + @ check only (display escaped in legal pages)
    if "contact_email" in data and data["contact_email"]:
        email = str(data["contact_email"]).strip()[:254]
        if "@" not in email or "<" in email or ">" in email or '"' in email:
            raise HTTPException(status_code=400, detail="Email de contact invalide")
        data["contact_email"] = email
        data["email"] = email

    allowed_keys = {
        "contact_email",
        "email",
        "intro_text",
        "social_links",
        "instagram",
        "tiktok",
    }
    async with async_session_maker() as session:
        for key, value in data.items():
            if key not in allowed_keys:
                continue
            result = await session.execute(select(Setting).where(Setting.key == key))
            s = result.scalar_one_or_none()
            stored = str(value) if value is not None else ""
            if key == "intro_text":
                stored = stored[:5000]
            if s:
                s.value = stored
            else:
                session.add(Setting(key=key, value=stored))
        await session.commit()
    return {"ok": True}


@router.post("/test-email")
async def send_test_email_api(
    request: Request,
    _: bool = Depends(require_admin),
):
    """Send sample order confirmation emails via SMTP (bypasses mock mode)."""
    from app.services.email import send_test_order_emails

    data = await request.json()
    to = (data.get("email") or "").strip()
    if not to or "@" not in to:
        raise HTTPException(status_code=400, detail="Adresse e-mail invalide")

    cfg = get_settings()
    if not cfg.smtp_host:
        raise HTTPException(
            status_code=400,
            detail="SMTP non configuré (SMTP_HOST manquant dans .env)",
        )

    results = send_test_order_emails(to=to)
    if not any(results.values()):
        raise HTTPException(
            status_code=502,
            detail="Échec envoi — vérifiez SMTP_USER, SMTP_PASSWORD et les logs",
        )

    return {
        "ok": True,
        "mock_mode": cfg.emails_mocked,
        "results": results,
        "hint": (
            "E-mails de test envoyés via SMTP."
            if not cfg.emails_mocked
            else "Mode mock actif pour les commandes, mais ce test utilise le SMTP réel."
        ),
    }


# --- Orders ---


@router.delete("/orders/{order_id}")
async def delete_order(
    order_id: int,
    request: Request,
    _: bool = Depends(require_admin),
):
    from app.models import Order, OrderItem

    async with async_session_maker() as session:
        result = await session.execute(select(Order).where(Order.id == order_id))
        order = result.scalar_one_or_none()
        if not order:
            raise HTTPException(status_code=404, detail="Commande non trouvée")
        items = (
            await session.execute(select(OrderItem).where(OrderItem.order_id == order.id))
        ).scalars().all()
        for item in items:
            await session.delete(item)
        await session.delete(order)
        await session.commit()
        logger.info("DELETE /api/orders/%s -> deleted", order_id)
        return {"ok": True}


@router.post("/orders/delete-bulk")
async def delete_orders_bulk(
    request: Request,
    _: bool = Depends(require_admin),
):
    from app.models import Order, OrderItem

    data = await request.json()
    ids = data.get("ids") if isinstance(data, dict) else None
    if not isinstance(ids, list) or not ids:
        raise HTTPException(status_code=400, detail="Liste d'identifiants requise")
    clean_ids = []
    for value in ids:
        try:
            clean_ids.append(int(value))
        except (TypeError, ValueError):
            continue
    if not clean_ids:
        raise HTTPException(status_code=400, detail="Aucun identifiant valide")

    deleted = 0
    async with async_session_maker() as session:
        result = await session.execute(select(Order).where(Order.id.in_(clean_ids)))
        orders = list(result.scalars().all())
        for order in orders:
            items = (
                await session.execute(select(OrderItem).where(OrderItem.order_id == order.id))
            ).scalars().all()
            for item in items:
                await session.delete(item)
            await session.delete(order)
            deleted += 1
        await session.commit()
    logger.info("POST /api/orders/delete-bulk -> deleted %s", deleted)
    return {"ok": True, "deleted": deleted}


# --- Referrals ---


@router.get("/referrals")
async def list_referrals(request: Request, _: bool = Depends(require_admin)):
    from app.models import ReferralLink, ReferralVisit

    async with async_session_maker() as session:
        result = await session.execute(select(ReferralLink).order_by(ReferralLink.name))
        output = []
        for r in result.scalars().all():
            count_res = await session.execute(
                select(func.count(ReferralVisit.id)).where(ReferralVisit.referral_id == r.id)
            )
            visits = count_res.scalar() or 0
            output.append(
                {
                    "id": r.id,
                    "name": r.name,
                    "code": r.code,
                    "visits_count": visits,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
            )
        output.sort(key=lambda x: x["visits_count"], reverse=True)
        return output


@router.post("/referrals")
async def create_referral(
    request: Request,
    name: str = Form(...),
    code: str = Form(...),
    _: bool = Depends(require_admin),
):
    from app.models import ReferralLink

    code = code.strip().lower().replace(" ", "_")[:100]
    async with async_session_maker() as session:
        result = await session.execute(select(ReferralLink).where(ReferralLink.code == code))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Ce code existe déjà")
        ref = ReferralLink(name=name.strip(), code=code)
        session.add(ref)
        await session.commit()
        await session.refresh(ref)
        return {"id": ref.id, "name": ref.name, "code": ref.code}


@router.delete("/referrals/{referral_id}")
async def delete_referral(
    referral_id: int,
    request: Request,
    _: bool = Depends(require_admin),
):
    from app.models import ReferralLink

    async with async_session_maker() as session:
        result = await session.execute(select(ReferralLink).where(ReferralLink.id == referral_id))
        ref = result.scalar_one_or_none()
        if not ref:
            raise HTTPException(status_code=404, detail="Parrain non trouvé")
        await session.delete(ref)
        await session.commit()
        return {"ok": True}
