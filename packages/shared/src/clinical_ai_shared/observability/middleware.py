import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from clinical_ai_shared.observability.logging import get_logger, set_correlation_id

logger = get_logger(__name__)

class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Middleware to manage Correlation ID per request."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        set_correlation_id(correlation_id)
        
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log every request."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.perf_counter()
        
        response = await call_next(request)
        
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        
        logger.info(
            "http_request",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        
        return response
