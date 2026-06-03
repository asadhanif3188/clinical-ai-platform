"""API key authentication middleware.

Reads the ``X-API-Key`` request header and validates it against the configured
list of valid keys (``settings.api_keys``).

Behaviour:
- Paths in ``UNAUTHENTICATED_PATHS`` (health/readiness probes) are always
  allowed through without a key.
- If ``api_keys`` is an empty list (dev / test mode), all requests pass through.
- Otherwise a missing or unrecognised key returns HTTP 401.
"""

from __future__ import annotations

import json
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from clinical_ai_shared.observability.logging import get_logger

logger = get_logger(__name__)

# Paths that are always allowed through — liveness / readiness probes must
# not require authentication so that Kubernetes / load-balancer health checks
# keep working without managing API keys.
_UNAUTHENTICATED_PATHS: frozenset[str] = frozenset({"/health", "/ready"})

_UNAUTHORIZED_BODY = json.dumps({"detail": "Invalid or missing API key"}).encode()


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Validates the ``X-API-Key`` header on every authenticated request.

    Args:
        app: The ASGI application to wrap.
        api_keys: List of accepted keys. Pass an empty list to disable
                  authentication entirely (dev / test mode).
    """

    def __init__(self, app, api_keys: list[str]) -> None:  # type: ignore[override]
        super().__init__(app)
        self._api_keys: frozenset[str] = frozenset(api_keys)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in _UNAUTHENTICATED_PATHS:
            return await call_next(request)

        # Empty key set → auth disabled (dev / test mode).
        if not self._api_keys:
            return await call_next(request)

        incoming_key = request.headers.get("X-API-Key")
        if not incoming_key or incoming_key not in self._api_keys:
            logger.warning(
                "api_key_rejected",
                path=request.url.path,
                method=request.method,
                has_key=bool(incoming_key),
            )
            return Response(
                content=_UNAUTHORIZED_BODY,
                status_code=401,
                media_type="application/json",
            )

        return await call_next(request)
