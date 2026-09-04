"""SumUp Hosted Checkout helpers."""

from __future__ import annotations

import uuid
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logger import logger

SUMUP_API_BASE = "https://api.sumup.com/v0.1"


def sumup_configured() -> bool:
    cfg = get_settings()
    return bool(cfg.sumup_api_key and cfg.sumup_merchant_code)


def create_hosted_checkout(
    *,
    amount: float,
    description: str,
    redirect_url: str,
    currency: str = "EUR",
    checkout_reference: str | None = None,
) -> dict[str, Any]:
    """
    Create a SumUp Hosted Checkout session.
    Returns the API response including hosted_checkout_url and id.
    Raises httpx.HTTPError or ValueError on failure.
    """
    cfg = get_settings()
    if not sumup_configured():
        raise ValueError("SumUp non configuré")

    ref = checkout_reference or str(uuid.uuid4())
    # Keep reference in return URL so success page can verify without session
    sep = "&" if "?" in redirect_url else "?"
    redirect_with_ref = f"{redirect_url}{sep}checkout_reference={ref}"

    payload = {
        "checkout_reference": ref,
        "amount": round(float(amount), 2),
        "currency": currency,
        "merchant_code": cfg.sumup_merchant_code,
        "description": description[:100],
        "redirect_url": redirect_with_ref,
        "hosted_checkout": {"enabled": True},
    }

    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            f"{SUMUP_API_BASE}/checkouts",
            headers={
                "Authorization": f"Bearer {cfg.sumup_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        if response.is_error:
            logger.error(
                "SumUp checkout create failed: %s %s",
                response.status_code,
                response.text,
            )
            response.raise_for_status()
        data = response.json()

    if not data.get("hosted_checkout_url"):
        raise ValueError("SumUp n'a pas renvoyé d'URL Hosted Checkout")
    return data


def get_checkout(checkout_id: str) -> dict[str, Any] | None:
    """Retrieve a checkout by id. Returns None if not found / not configured."""
    cfg = get_settings()
    if not sumup_configured() or not checkout_id:
        return None

    with httpx.Client(timeout=20.0) as client:
        response = client.get(
            f"{SUMUP_API_BASE}/checkouts/{checkout_id}",
            headers={"Authorization": f"Bearer {cfg.sumup_api_key}"},
        )
        if response.status_code == 404:
            return None
        if response.is_error:
            logger.error(
                "SumUp checkout get failed: %s %s",
                response.status_code,
                response.text,
            )
            return None
        return response.json()


def find_checkout_by_reference(checkout_reference: str) -> dict[str, Any] | None:
    """Find a checkout by checkout_reference."""
    cfg = get_settings()
    if not sumup_configured() or not checkout_reference:
        return None

    with httpx.Client(timeout=20.0) as client:
        response = client.get(
            f"{SUMUP_API_BASE}/checkouts",
            headers={"Authorization": f"Bearer {cfg.sumup_api_key}"},
            params={"checkout_reference": checkout_reference},
        )
        if response.is_error:
            logger.error(
                "SumUp checkout list failed: %s %s",
                response.status_code,
                response.text,
            )
            return None
        data = response.json()
        if isinstance(data, list) and data:
            return data[0]
        if isinstance(data, dict):
            return data
        return None


def is_checkout_paid(checkout: dict[str, Any] | None) -> bool:
    if not checkout:
        return False
    status = str(checkout.get("status") or "").upper()
    if status in {"PAID", "SUCCESSFUL"}:
        return True
    for tx in checkout.get("transactions") or []:
        if str(tx.get("status") or "").upper() in {"SUCCESSFUL", "PAID"}:
            return True
    return False
