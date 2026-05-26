from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WorkflowStatus(str, Enum):
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class WorkflowState(BaseModel):
    run_id: UUID
    workflow_name: str
    status: WorkflowStatus
    current_node: str
    checkpoint: dict[str, Any] = Field(..., description="Full LangGraph state snapshot")
    started_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "run_id": "550e8400-e29b-41d4-a716-446655440000",
                "workflow_name": "triage_pipeline",
                "status": "running",
                "current_node": "intake_agent",
                "checkpoint": {"messages": [], "retry_count": 0},
                "started_at": "2026-05-26T10:00:00Z",
                "updated_at": "2026-05-26T10:05:00Z",
            }
        }
    )


class NodeType(str, Enum):
    AGENT = "agent"
    HUMAN_GATEWAY = "human_gateway"


class RetryConfig(BaseModel):
    max_attempts: int = 3
    backoff_seconds: int = 5


class NotificationConfig(BaseModel):
    channel: str
    message: str


class NodeDefinition(BaseModel):
    id: str
    agent: str
    type: NodeType = NodeType.AGENT
    timeout_seconds: int = 60
    retry: RetryConfig | None = None
    notification: NotificationConfig | None = None


class EdgeDefinition(BaseModel):
    from_node: str
    to_node: str
    condition: str | None = None
    max_loops: int = 3


class StateFieldDefinition(BaseModel):
    name: str
    type_hint: str
    nullable: bool = True


class WorkflowDefinition(BaseModel):
    name: str
    version: str
    description: str | None = None
    state_schema: list[StateFieldDefinition]
    nodes: list[NodeDefinition]
    edges: list[EdgeDefinition]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "triage_pipeline",
                "version": "1.0.0",
                "state_schema": [{"name": "document_id", "type_hint": "str"}],
                "nodes": [{"id": "intake", "agent": "intake_agent"}],
                "edges": [{"from_node": "intake", "to_node": "END"}],
            }
        }
    )


class NodeResult(BaseModel):
    node_id: str
    output: dict[str, Any]
    cost_usd: float = 0.0
    duration_ms: int = 0
    timestamp: datetime = Field(default_factory=datetime.now)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "node_id": "intake",
                "output": {"document_type": "lab_report"},
                "cost_usd": 0.002,
                "duration_ms": 1500,
                "timestamp": "2026-05-26T10:00:00Z",
            }
        }
    )
