"""Workflow definition models for ClinFlow AI.

These models represent the schema for YAML-defined workflows. They are distinct from
the shared API schemas in clinical_ai_shared.schemas.workflow, which are used for
runtime state and API serialization. These models include validation logic specific
to workflow execution safety.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

# NodeType as a Literal to allow string comparison without enum indirection
NodeType = Literal["agent", "human_gateway"]


class RetryConfig(BaseModel):
    max_attempts: int = Field(default=3, ge=1)
    backoff_seconds: int = Field(default=5, ge=0)


class NotificationConfig(BaseModel):
    channel: str
    message: str


class NodeDefinition(BaseModel):
    id: str
    agent: str | None = None
    type: NodeType = "agent"
    timeout_seconds: int = Field(default=60, gt=0)
    retry: RetryConfig | None = None
    notification: NotificationConfig | None = None
    # Human-in-the-loop specific — ignored for agent nodes
    assignee_role: str | None = None

    @model_validator(mode="after")
    def validate_agent_required(self) -> NodeDefinition:
        if self.type == "agent" and self.agent is None:
            raise ValueError(
                f"Node '{self.id}' has type 'agent' but is missing required 'agent' field."
            )
        return self


class EdgeDefinition(BaseModel):
    from_node: str
    to_node: str
    condition: str | None = None
    max_loops: int = Field(default=3, ge=0)


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

    @model_validator(mode="after")
    def validate_edge_node_ids(self) -> WorkflowDefinition:
        """All from_node and to_node values must reference known node IDs or the sentinel 'END'."""
        known_ids = {node.id for node in self.nodes} | {"END"}
        for edge in self.edges:
            if edge.from_node not in known_ids:
                raise ValueError(
                    f"Edge has unknown from_node '{edge.from_node}'. "
                    f"Known node IDs: {sorted(known_ids - {'END'})}"
                )
            if edge.to_node not in known_ids:
                raise ValueError(
                    f"Edge has unknown to_node '{edge.to_node}'. "
                    f"Known node IDs: {sorted(known_ids - {'END'})}"
                )
        return self

    @model_validator(mode="after")
    def validate_terminal_nodes(self) -> WorkflowDefinition:
        """At least one terminal node must exist.

        A terminal node is a node with no outgoing edges. The special sentinel 'END'
        as a to_node also satisfies this requirement.
        """
        node_ids_with_outgoing = {edge.from_node for edge in self.edges}
        all_node_ids = {node.id for node in self.nodes}
        natural_terminals = all_node_ids - node_ids_with_outgoing
        has_end_target = any(edge.to_node == "END" for edge in self.edges)

        if not natural_terminals and not has_end_target:
            raise ValueError(
                "Workflow has no terminal nodes. At least one node must have no "
                "outgoing edges, or at least one edge must point to 'END'. "
                "This usually indicates an unresolvable cycle."
            )
        return self
