"""Logging configuration."""

import sys
from pathlib import Path

from loguru import logger as _logger

_logger.remove()
_logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level="INFO",
)

log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
_logger.add(
    log_dir / "app.log",
    rotation="500 KB",
    retention="7 days",
    level="DEBUG",
)
# NIS2: separate security audit log (retention 90 days for incident handling)
_logger.add(
    log_dir / "security.log",
    rotation="1 MB",
    retention="90 days",
    level="WARNING",
    filter=lambda r: "SECURITY" in str(r["message"]),
)

logger = _logger


def security_log(event: str, **kwargs) -> None:
    """NIS2: security audit log for incidents and auth events."""
    parts = [f"SECURITY [{event}]"]
    for k, v in kwargs.items():
        if v is not None:
            parts.append(f"{k}={v}")
    logger.warning(" | ".join(parts))
