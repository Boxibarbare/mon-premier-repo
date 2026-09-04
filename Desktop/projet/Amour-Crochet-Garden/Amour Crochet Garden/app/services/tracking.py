"""Page view and referral tracking."""

import hashlib
import hmac

from starlette.requests import Request

from app.core.config import get_settings
from app.core.database import async_session_maker
from app.models import PageView, ReferralLink, ReferralVisit


def _ip_hash(request: Request) -> str:
    """HMAC-hash client IP (pepper from SECRET_KEY) for anonymization."""
    ip = (request.client.host if request.client else "") or "unknown"
    pepper = get_settings().secret_key.encode("utf-8")
    return hmac.new(pepper, ip.encode("utf-8"), hashlib.sha256).hexdigest()


async def record_page_view(request: Request, path: str, referral_code: str | None = None) -> None:
    """Record a page view."""
    try:
        async with async_session_maker() as session:
            session.add(
                PageView(
                    path=path,
                    ip_hash=_ip_hash(request),
                    referral_code=referral_code,
                )
            )
            await session.commit()
    except Exception:
        pass


async def record_referral_visit(request: Request, referral_code: str) -> None:
    """Record a referral visit if code exists."""
    try:
        from sqlalchemy import select

        async with async_session_maker() as session:
            result = await session.execute(
                select(ReferralLink).where(ReferralLink.code == referral_code.strip())
            )
            ref = result.scalar_one_or_none()
            if ref:
                session.add(
                    ReferralVisit(
                        referral_id=ref.id,
                        ip_hash=_ip_hash(request),
                    )
                )
                await session.commit()
    except Exception:
        pass
