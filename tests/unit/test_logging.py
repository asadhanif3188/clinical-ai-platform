import io
import json
import uuid

import structlog
from clinical_ai_shared.config import settings
from clinical_ai_shared.observability.logging import (
    configure_logging,
    get_logger,
    set_correlation_id,
)


def test_logger_correlation_id(monkeypatch):
    # Force JSON output for testing
    monkeypatch.setattr(settings, "debug", False)

    # Reset structlog configuration to apply settings change
    # Note: structlog doesn't easily allow resetting, but we can re-configure it
    configure_logging()

    # Capture output
    log_output = io.StringIO()
    structlog.configure(
        logger_factory=structlog.PrintLoggerFactory(log_output),
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            # Add our custom processor
            lambda _l, _m, event_dict: (
                {**event_dict, "correlation_id": "test-id"}
                if "correlation_id" not in event_dict
                else event_dict
            ),
            structlog.processors.JSONRenderer(),
        ],
    )

    logger = get_logger("test")
    assert logger is not None

    # We can't easily capture the exact output from the global config because we already called it
    # Let's try a more direct approach for the unit test

    output = io.StringIO()
    # Configure a local logger for testing the processors logic
    from clinical_ai_shared.observability.logging import add_correlation_id

    test_processors = [add_correlation_id, structlog.processors.JSONRenderer()]

    # Mock correlation id
    test_id = str(uuid.uuid4())
    set_correlation_id(test_id)

    # Manual execution of processors to verify logic
    event_dict = {"event": "test_event"}
    processed_event = add_correlation_id(None, "info", event_dict)

    assert processed_event["correlation_id"] == test_id

    # Verify JSON rendering
    json_output = structlog.processors.JSONRenderer()(None, "info", processed_event)
    data = json.loads(json_output)
    assert data["event"] == "test_event"
    assert data["correlation_id"] == test_id


def test_get_logger_returns_logger():
    logger = get_logger("test_name")
    # In newer structlog versions, it might be a Proxy, but it behaves like a logger
    assert hasattr(logger, "info")
    assert hasattr(logger, "error")
