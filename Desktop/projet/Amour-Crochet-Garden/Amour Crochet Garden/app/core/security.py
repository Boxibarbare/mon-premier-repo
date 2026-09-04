"""Authentication and session management."""

import re
import secrets
import time
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

import bcrypt
from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import async_session_maker
from app.models import Admin

_SAFE_IMAGE_PATH = re.compile(
    r"^uploads/[0-9a-fA-F-]{36}\.(jpg|jpeg|png|gif|webp)$"
)
_SAFE_URL_SCHEMES = frozenset({"http", "https", "mailto"})


def hash_password(password: str) -> str:
    """Hash a password with bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


async def get_or_create_admin(session: AsyncSession) -> Admin:
    """Create default admin if none exists."""
    settings = get_settings()
    result = await session.execute(select(Admin).limit(1))
    admin = result.scalar_one_or_none()
    if admin is None:
        admin = Admin(
            username=settings.admin_username,
            password_hash=hash_password(settings.admin_password),
        )
        session.add(admin)
        await session.commit()
        await session.refresh(admin)
    return admin


async def authenticate_admin(username: str, password: str) -> Admin | None:
    """Authenticate admin by username and password."""
    async with async_session_maker() as session:
        result = await session.execute(select(Admin).where(Admin.username == username))
        admin = result.scalar_one_or_none()
        if admin and verify_password(password, admin.password_hash):
            return admin
    return None


def create_session_token() -> str:
    """Generate a secure session token."""
    return secrets.token_urlsafe(32)


def get_admin_session(request: Request) -> str | None:
    """Get admin session from request."""
    return request.session.get("admin_session")


def generate_csrf_token() -> str:
    """Generate a CSRF token."""
    return secrets.token_urlsafe(32)


def verify_csrf(session_token: str | None, submitted: str | None) -> bool:
    """Constant-time CSRF comparison."""
    if not session_token or not submitted:
        return False
    return secrets.compare_digest(str(session_token), str(submitted))


def ensure_admin_csrf(request: Request) -> str:
    """Ensure an admin CSRF token exists in session and return it."""
    token = request.session.get("admin_csrf")
    if not token:
        token = generate_csrf_token()
        request.session["admin_csrf"] = token
    return token


def is_safe_external_url(url: str) -> bool:
    """Allow only http(s)/mailto URLs (blocks javascript:, data:, etc.)."""
    if not url or not isinstance(url, str):
        return False
    url = url.strip()
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    if parsed.scheme.lower() not in _SAFE_URL_SCHEMES:
        return False
    if parsed.scheme.lower() in ("http", "https") and not parsed.netloc:
        return False
    return True


def is_safe_image_path(path: str | None) -> bool:
    """Validate stored product image paths (prevent path traversal)."""
    if not path:
        return True
    return bool(_SAFE_IMAGE_PATH.match(path.replace("\\", "/")))


def is_sumup_checkout_url(url: str) -> bool:
    """Validate SumUp hosted checkout redirect target."""
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    if parsed.scheme != "https":
        return False
    host = (parsed.hostname or "").lower()
    return host == "checkout.sumup.com" or host.endswith(".sumup.com")


# Rate limiting: {ip: [(timestamp, ), ...]}
_rate_limit_store: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT_MAX = 5
_RATE_LIMIT_WINDOW = 3600  # 1 hour in seconds


def check_rate_limit(ip: str) -> bool:
    """Return True if allowed, False if rate limited."""
    now = time.time()
    _rate_limit_store[ip] = [t for t in _rate_limit_store[ip] if now - t < _RATE_LIMIT_WINDOW]
    if len(_rate_limit_store[ip]) >= _RATE_LIMIT_MAX:
        return False
    _rate_limit_store[ip].append(now)
    return True


# Admin login rate limiting (failures only)
_admin_login_store: dict[str, list[float]] = defaultdict(list)
_ADMIN_LOGIN_MAX = 5
_ADMIN_LOGIN_WINDOW = 900  # 15 minutes


def check_admin_login_rate_limit(ip: str) -> bool:
    """Return True if allowed, False if rate limited (brute-force protection)."""
    now = time.time()
    _admin_login_store[ip] = [
        t for t in _admin_login_store[ip] if now - t < _ADMIN_LOGIN_WINDOW
    ]
    return len(_admin_login_store[ip]) < _ADMIN_LOGIN_MAX


def record_admin_login_failure(ip: str) -> None:
    """Record a failed admin login attempt for rate limiting."""
    now = time.time()
    _admin_login_store[ip] = [
        t for t in _admin_login_store[ip] if now - t < _ADMIN_LOGIN_WINDOW
    ]
    _admin_login_store[ip].append(now)


# Checkout rate limiting
_checkout_store: dict[str, list[float]] = defaultdict(list)
_CHECKOUT_MAX = 10
_CHECKOUT_WINDOW = 3600


def check_checkout_rate_limit(ip: str) -> bool:
    now = time.time()
    _checkout_store[ip] = [t for t in _checkout_store[ip] if now - t < _CHECKOUT_WINDOW]
    if len(_checkout_store[ip]) >= _CHECKOUT_MAX:
        return False
    _checkout_store[ip].append(now)
    return True


# NIS2: file upload validation - allowed image types
_ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
_MAGIC_TO_EXT = {
    "jpeg": ".jpg",
    "png": ".png",
    "gif": ".gif",
    "webp": ".webp",
}


def detect_image_type(content: bytes) -> str | None:
    if len(content) < 12:
        return None
    if content[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if content[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if content[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "webp"
    return None


def validate_uploaded_image(content: bytes, filename: str) -> tuple[bool, str]:
    """
    Validate uploaded image: extension whitelist + magic bytes.
    Returns (is_valid, error_message).
    """
    ext = Path(filename).suffix.lower() if filename else ""
    if ext not in _ALLOWED_IMAGE_EXTENSIONS:
        return False, f"Extension non autorisée: {ext or '(aucune)'}"
    kind = detect_image_type(content)
    if not kind:
        return False, "Type de fichier non reconnu (image invalide)"
    if kind == "jpeg" and ext in (".jpg", ".jpeg"):
        return True, ""
    if _MAGIC_TO_EXT[kind] == ext:
        return True, ""
    return False, "Extension incohérente avec le contenu du fichier"


def extension_for_image_content(content: bytes) -> str:
    """Return safe file extension derived from magic bytes."""
    kind = detect_image_type(content)
    return _MAGIC_TO_EXT.get(kind or "", ".jpg")
