"""NIS2-compliant security headers and middleware."""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import get_settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Add security headers per NIS2, OWASP, and CIS benchmarks.
    - CSP: Content Security Policy (XSS, injection)
    - HSTS: HTTP Strict Transport Security
    - X-Frame-Options: Clickjacking
    - X-Content-Type-Options: MIME sniffing
    - Referrer-Policy: Leak prevention
    - Permissions-Policy: Feature restrictions
    """

    # CSP: allow our origin, fonts, SumUp hosted checkout
    _CSP_BASE = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://checkout.sumup.com https://*.sumup.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://checkout.sumup.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: https: blob:; "
        "frame-src 'self' https://checkout.sumup.com https://*.sumup.com; "
        "connect-src 'self' https://api.sumup.com https://*.sumup.com; "
        "base-uri 'self'; "
        "form-action 'self' https://checkout.sumup.com https://*.sumup.com; "
        "frame-ancestors 'self'; "
        "object-src 'none'"
    )

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        self._add_headers(response)
        return response

    def _add_headers(self, response):
        """Add security headers to response."""
        settings = get_settings()
        headers = response.headers
        headers["X-Content-Type-Options"] = "nosniff"
        headers["X-Frame-Options"] = "SAMEORIGIN"
        headers["X-XSS-Protection"] = "1; mode=block"
        headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
            "magnetometer=(), microphone=(), payment=(self), usb=()"
        )
        csp = self._CSP_BASE
        if not settings.debug:
            csp += "; upgrade-insecure-requests"
        headers["Content-Security-Policy"] = csp
        # HSTS when HTTPS-only (production), not merely when debug is off
        if settings.https_only or not settings.debug:
            headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains; preload"
            )
