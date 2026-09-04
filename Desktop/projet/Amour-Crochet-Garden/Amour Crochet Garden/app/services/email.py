"""Transactional email helpers (SMTP + mock en mode dev)."""

from __future__ import annotations

import re
import smtplib
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

from app.core.config import get_settings
from app.core.logger import logger
from app.services.email_templates import (
    build_admin_notification,
    build_customer_confirmation,
)

_EMAILS_DIR = Path(__file__).resolve().parent.parent.parent / "logs" / "emails"


def email_configured() -> bool:
    cfg = get_settings()
    if cfg.emails_mocked:
        return True
    return bool(cfg.smtp_host and (cfg.smtp_from or cfg.smtp_user or cfg.contact_email))


def _from_address() -> str:
    cfg = get_settings()
    return (cfg.smtp_from or cfg.smtp_user or cfg.contact_email or "dev@localhost").strip()


def _admin_notify_address() -> str:
    cfg = get_settings()
    return (cfg.order_notify_email or cfg.contact_email or "admin@localhost").strip()


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._@+-]+", "_", value.strip())
    return cleaned[:60] or "mail"


def _write_mock_email(
    *, to: str, subject: str, body: str, html_body: str | None = None
) -> Path:
    _EMAILS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    base = f"{stamp}_{_safe_filename(to)}_{_safe_filename(subject)}"
    path = _EMAILS_DIR / f"{base}.txt"
    content = (
        f"From: {_from_address()}\n"
        f"To: {to}\n"
        f"Subject: {subject}\n"
        f"{'=' * 60}\n"
        f"{body}\n"
    )
    path.write_text(content, encoding="utf-8")
    if html_body:
        html_path = _EMAILS_DIR / f"{base}.html"
        html_path.write_text(html_body, encoding="utf-8")
    logger.info(
        "MOCK EMAIL -> %s | %s | fichier=%s\n%s",
        to,
        subject,
        path,
        body,
    )
    return path


def send_email(
    *,
    to: str,
    subject: str,
    body: str,
    html_body: str | None = None,
    force_smtp: bool = False,
) -> bool:
    """Send an email (plain text + optional HTML). Returns True on success."""
    cfg = get_settings()
    if not to:
        return False

    if cfg.emails_mocked and not force_smtp:
        _write_mock_email(to=to, subject=subject, body=body, html_body=html_body)
        return True

    if not force_smtp and not email_configured():
        logger.warning("Email non envoyé (SMTP non configuré): %s -> %s", subject, to)
        return False

    if force_smtp and not cfg.smtp_host:
        logger.warning("Email test non envoyé (SMTP_HOST manquant): %s -> %s", subject, to)
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = _from_address()
    msg["To"] = to
    msg.set_content(body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")

    try:
        with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=30) as smtp:
            if cfg.smtp_use_tls:
                smtp.starttls()
            if cfg.smtp_user and cfg.smtp_password:
                smtp.login(cfg.smtp_user, cfg.smtp_password)
            smtp.send_message(msg)
        logger.info("Email envoyé: %s -> %s", subject, to)
        return True
    except Exception:
        logger.exception("Échec envoi email: %s -> %s", subject, to)
        return False


def send_customer_order_confirmation(
    *,
    customer_name: str,
    customer_email: str,
    reference: str,
    subtotal: float,
    shipping_fee: float,
    total: float,
    shipping_address: str,
    items: list[dict],
    force_smtp: bool = False,
) -> bool:
    text_body, html_body = build_customer_confirmation(
        customer_name=customer_name,
        reference=reference,
        subtotal=subtotal,
        shipping_fee=shipping_fee,
        total=total,
        shipping_address=shipping_address,
        items=items,
    )
    return send_email(
        to=customer_email,
        subject=f"Paiement confirmé — commande {reference}",
        body=text_body,
        html_body=html_body,
        force_smtp=force_smtp,
    )


def send_admin_order_notification(
    *,
    customer_name: str,
    customer_email: str,
    customer_phone: str | None,
    reference: str,
    subtotal: float,
    shipping_fee: float,
    total: float,
    shipping_address: str,
    items: list[dict],
    force_smtp: bool = False,
) -> bool:
    text_body, html_body = build_admin_notification(
        customer_name=customer_name,
        customer_email=customer_email,
        customer_phone=customer_phone,
        reference=reference,
        subtotal=subtotal,
        shipping_fee=shipping_fee,
        total=total,
        shipping_address=shipping_address,
        items=items,
    )
    return send_email(
        to=_admin_notify_address(),
        subject=f"Nouvelle commande {reference} — {total:.2f} €",
        body=text_body,
        html_body=html_body,
        force_smtp=force_smtp,
    )


def send_test_order_emails(*, to: str) -> dict[str, bool]:
    """Send sample customer + admin emails (always via SMTP when configured)."""
    sample_items = [
        {"product_name": "Amigurumi lapin (test)", "quantity": 1, "unit_price": 28.0},
        {"product_name": "Porte-clés fleur (test)", "quantity": 2, "unit_price": 8.0},
    ]
    subtotal = 44.0
    shipping_fee = 5.0
    total = 49.0
    reference = "TEST-DEV"

    customer_ok = send_customer_order_confirmation(
        customer_name="Test Client",
        customer_email=to,
        reference=reference,
        subtotal=subtotal,
        shipping_fee=shipping_fee,
        total=total,
        shipping_address="12 rue des Fleurs\n75001 Paris\nFrance",
        items=sample_items,
        force_smtp=True,
    )
    admin_ok = send_admin_order_notification(
        customer_name="Test Client",
        customer_email=to,
        customer_phone="06 00 00 00 00",
        reference=reference,
        subtotal=subtotal,
        shipping_fee=shipping_fee,
        total=total,
        shipping_address="12 rue des Fleurs\n75001 Paris\nFrance",
        items=sample_items,
        force_smtp=True,
    )
    return {"customer": customer_ok, "admin": admin_ok}
