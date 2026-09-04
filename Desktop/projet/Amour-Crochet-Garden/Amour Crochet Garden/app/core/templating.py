"""Jinja2 helpers compatible with Starlette 1.0+ TemplateResponse API."""

from __future__ import annotations

from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates
from starlette.responses import Response


def create_templates(base_dir: Path) -> Jinja2Templates:
    return Jinja2Templates(directory=str(base_dir / "templates"))


def render(
    templates: Jinja2Templates,
    request: Request,
    name: str,
    context: dict | None = None,
    *,
    status_code: int = 200,
) -> Response:
    """Render a template (Starlette 1.0: request, name, context)."""
    ctx = {k: v for k, v in (context or {}).items() if k != "request"}
    return templates.TemplateResponse(request, name, ctx, status_code=status_code)
