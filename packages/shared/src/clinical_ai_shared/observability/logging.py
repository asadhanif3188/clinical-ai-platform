import logging
import sys
from contextvars import ContextVar
from typing import Any, Optional

import structlog
from structlog.types import Processor

from clinical_ai_shared.config import settings

# Context variable to store correlation_id
correlation_id_ctx: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)

def set_correlation_id(correlation_id: str) -> None:
    correlation_id_ctx.set(correlation_id)

def get_correlation_id() -> Optional[str]:
    return correlation_id_ctx.get()

def add_correlation_id(
    _logger: logging.Logger, _method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Processor to add correlation_id from contextvars."""
    correlation_id = get_correlation_id()
    if correlation_id:
        event_dict["correlation_id"] = correlation_id
    return event_dict

def configure_logging() -> None:
    """Configure structlog based on settings."""
    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        add_correlation_id,
        structlog.processors.UnicodeDecoder(),
    ]

    if settings.debug:
        # Development: Pretty print with colors
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
    else:
        # Production: JSON output
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        logger_factory=structlog.PrintLoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level.upper(), logging.INFO)
        ),
        cache_logger_on_first_use=True,
    )

def get_logger(name: Optional[str] = None) -> structlog.BoundLogger:
    """Get a structured logger."""
    # Ensure logging is configured
    if not structlog.is_configured():
        configure_logging()
    
    logger = structlog.get_logger(name)
    return logger
