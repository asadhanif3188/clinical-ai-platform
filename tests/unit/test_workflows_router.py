"""Unit tests for the /api/v1/workflows router and APIKeyMiddleware.

Uses FastAPI TestClient (synchronous) with mocked loaders and DB sessions so
no infrastructure is required.

Coverage:
1. GET /api/v1/workflows returns list of workflow definitions (mocked).
2. GET /api/v1/workflows/runs/{invalid_id} returns 404.
3. POST /api/v1/workflows/runs/{id}/resume with invalid decision returns 422.
4. Missing API key returns 401 when api_keys are configured.
5. Valid API key passes through.
6. Health/ready probes are always allowed without a key.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers import workflows as workflows_module
from api.routers.workflows import router as workflows_router
from clinical_ai_shared.auth.middleware import APIKeyMiddleware
from clinical_ai_clinflow.definitions import (
    EdgeDefinition,
    NodeDefinition,
    StateFieldDefinition,
    WorkflowDefinition,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_workflow_def(name: str = "test_wf") -> WorkflowDefinition:
    """Minimal valid WorkflowDefinition for testing."""
    return WorkflowDefinition(
        name=name,
        version="1.0",
        description="Test workflow",
        state_schema=[StateFieldDefinition(name="input", type_hint="str")],
        nodes=[
            NodeDefinition(id="step_a", agent="agent_a"),
            NodeDefinition(id="step_b", agent="agent_b"),
        ],
        edges=[
            EdgeDefinition(from_node="step_a", to_node="step_b"),
            EdgeDefinition(from_node="step_b", to_node="END"),
        ],
    )


def _make_app(api_keys: list[str] | None = None) -> FastAPI:
    """Build a minimal FastAPI app with the workflows router and optional auth."""
    app = FastAPI()
    if api_keys is not None:
        app.add_middleware(APIKeyMiddleware, api_keys=api_keys)
    app.include_router(workflows_router)

    # Add a /health endpoint so we can test auth bypass.
    from fastapi import APIRouter
    health_router = APIRouter()

    @health_router.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @health_router.get("/ready")
    async def ready() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(health_router)
    return app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client_no_auth() -> TestClient:
    """App with no API key enforcement."""
    return TestClient(_make_app(api_keys=[]), raise_server_exceptions=True)


@pytest.fixture
def client_with_auth() -> TestClient:
    """App enforcing X-API-Key: secret-key."""
    return TestClient(_make_app(api_keys=["secret-key"]), raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Test: GET /api/v1/workflows — list definitions
# ---------------------------------------------------------------------------


def test_list_workflows_returns_summaries(client_no_auth: TestClient) -> None:
    """GET /api/v1/workflows should return a list of workflow summaries."""
    wf1 = _make_workflow_def("alpha")
    wf2 = _make_workflow_def("beta")

    with patch("api.routers.workflows._WORKFLOWS_DIR") as mock_dir:
        mock_dir.exists.return_value = True
        with patch("api.routers.workflows.list_workflows", return_value=[wf1, wf2]):
            resp = client_no_auth.get("/api/v1/workflows")

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 2
    names = {item["name"] for item in data}
    assert names == {"alpha", "beta"}
    assert data[0]["version"] == "1.0"


def test_list_workflows_empty_when_dir_missing(client_no_auth: TestClient) -> None:
    """GET /api/v1/workflows returns [] when the workflows directory does not exist."""
    with patch("api.routers.workflows._WORKFLOWS_DIR") as mock_dir:
        mock_dir.exists.return_value = False
        resp = client_no_auth.get("/api/v1/workflows")

    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# Test: GET /api/v1/workflows/runs/{run_id} — invalid / unknown run_id → 404
# ---------------------------------------------------------------------------


def test_get_run_invalid_uuid_returns_422(client_no_auth: TestClient) -> None:
    """Non-UUID run_id should be rejected by FastAPI path type validation (422)."""
    resp = client_no_auth.get("/api/v1/workflows/runs/not-a-valid-uuid")
    # FastAPI validates the UUID path parameter and returns 422 for bad values.
    assert resp.status_code == 422


def test_get_run_unknown_uuid_returns_404(client_no_auth: TestClient) -> None:
    """A valid UUID that does not match any run should return 404."""
    from api import dependencies

    mock_session = MagicMock()

    async def _fake_execute(*_args: Any, **_kwargs: Any) -> MagicMock:
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        return result

    mock_session.execute = _fake_execute

    async def _override_session():
        yield mock_session

    app = _make_app(api_keys=[])
    app.dependency_overrides[dependencies.get_session] = _override_session
    client = TestClient(app, raise_server_exceptions=True)

    unknown = str(uuid.uuid4())
    resp = client.get(f"/api/v1/workflows/runs/{unknown}")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Test: POST /api/v1/workflows/runs/{id}/resume — invalid decision → 422
# ---------------------------------------------------------------------------


def test_resume_invalid_decision_returns_422(client_no_auth: TestClient) -> None:
    """A decision value other than 'approved'/'rejected' must return 422."""
    from api import dependencies
    from clinical_ai_clinflow.human_gateway import HumanGatewayService

    mock_gateway = MagicMock(spec=HumanGatewayService)

    app = _make_app(api_keys=[])
    app.dependency_overrides[dependencies.get_gateway_service] = lambda: mock_gateway
    client = TestClient(app, raise_server_exceptions=True)

    run_id = str(uuid.uuid4())
    resp = client.post(
        f"/api/v1/workflows/runs/{run_id}/resume",
        json={"decision": "INVALID_VALUE", "reviewer_id": "user-1"},
    )
    assert resp.status_code == 422


def test_resume_missing_body_returns_422(client_no_auth: TestClient) -> None:
    """POST /resume with no body at all must return 422."""
    run_id = str(uuid.uuid4())
    resp = client_no_auth.post(f"/api/v1/workflows/runs/{run_id}/resume")
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Test: APIKeyMiddleware — 401 without key, pass with valid key
# ---------------------------------------------------------------------------


def test_missing_api_key_returns_401(client_with_auth: TestClient) -> None:
    """Requests without X-API-Key must be rejected with 401."""
    resp = client_with_auth.get("/api/v1/workflows")
    assert resp.status_code == 401
    assert "Invalid or missing API key" in resp.json()["detail"]


def test_wrong_api_key_returns_401(client_with_auth: TestClient) -> None:
    """Requests with an invalid key must be rejected with 401."""
    resp = client_with_auth.get(
        "/api/v1/workflows",
        headers={"X-API-Key": "wrong-key"},
    )
    assert resp.status_code == 401


def test_valid_api_key_allows_request(client_with_auth: TestClient) -> None:
    """A valid X-API-Key must allow the request through."""
    with patch("api.routers.workflows._WORKFLOWS_DIR") as mock_dir:
        mock_dir.exists.return_value = False
        resp = client_with_auth.get(
            "/api/v1/workflows",
            headers={"X-API-Key": "secret-key"},
        )
    assert resp.status_code == 200


def test_health_probe_bypasses_auth(client_with_auth: TestClient) -> None:
    """GET /health must always return 200 regardless of API key."""
    resp = client_with_auth.get("/health")
    assert resp.status_code == 200


def test_ready_probe_bypasses_auth(client_with_auth: TestClient) -> None:
    """GET /ready must always return 200 regardless of API key."""
    resp = client_with_auth.get("/ready")
    assert resp.status_code == 200
