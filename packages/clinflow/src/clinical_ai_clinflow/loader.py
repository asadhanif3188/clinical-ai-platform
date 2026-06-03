"""YAML workflow definition loader for ClinFlow AI.

Handles the impedance mismatch between YAML workflow files (which use `from`/`to`
because they're human-authored) and the Pydantic models (which use `from_node`/`to_node`
to avoid clashing with Python's `from` keyword).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from clinical_ai_clinflow.definitions import (
    EdgeDefinition,
    StateFieldDefinition,
    WorkflowDefinition,
)


def _parse_state_schema(raw: dict[str, Any] | list[Any]) -> list[StateFieldDefinition]:
    """Convert YAML state_schema to list[StateFieldDefinition].

    YAML format (dict):
        state_schema:
          input_data: str
          classification: str | null

    Direct list format is also accepted for programmatic use.
    """
    if isinstance(raw, list):
        return [StateFieldDefinition.model_validate(item) for item in raw]

    fields: list[StateFieldDefinition] = []
    for name, type_hint in raw.items():
        hint_str = str(type_hint)
        nullable = "null" in hint_str
        fields.append(StateFieldDefinition(name=name, type_hint=hint_str, nullable=nullable))
    return fields


def _parse_edges(raw_edges: list[dict[str, Any]]) -> list[EdgeDefinition]:
    """Convert YAML edges (from:/to:) to EdgeDefinition (from_node/to_node).

    YAML uses `from` and `to` because they read naturally. Pydantic uses
    `from_node` and `to_node` because `from` is a reserved Python keyword.
    """
    edges: list[EdgeDefinition] = []
    for raw in raw_edges:
        data: dict[str, Any] = {
            "from_node": raw["from"],
            "to_node": raw["to"],
        }
        if "condition" in raw:
            data["condition"] = raw["condition"]
        if "max_loops" in raw:
            data["max_loops"] = raw["max_loops"]
        edges.append(EdgeDefinition(**data))
    return edges


def _build_workflow(data: dict[str, Any]) -> WorkflowDefinition:
    """Convert a raw parsed YAML dict into a validated WorkflowDefinition."""
    state_schema = _parse_state_schema(data.get("state_schema", {}))
    edges = _parse_edges(data.get("edges", []))

    # Use .get() for all fields so missing required keys surface as Pydantic
    # ValidationError rather than KeyError.
    raw_version = data.get("version")
    return WorkflowDefinition.model_validate(
        {
            "name": data.get("name"),
            "version": str(raw_version) if raw_version is not None else None,
            "description": data.get("description"),
            "state_schema": state_schema,
            "nodes": data.get("nodes", []),
            "edges": edges,
        }
    )


def load_workflow(path: Path) -> WorkflowDefinition:
    """Load and validate a WorkflowDefinition from a YAML file.

    Args:
        path: Absolute or relative path to the .yml workflow file.

    Returns:
        A validated WorkflowDefinition.

    Raises:
        FileNotFoundError: If the path does not exist.
        yaml.YAMLError: If the file is not valid YAML.
        pydantic.ValidationError: If the workflow fails validation.
    """
    with path.open("r", encoding="utf-8") as fh:
        data: dict[str, Any] = yaml.safe_load(fh)
    return _build_workflow(data)


def load_workflow_from_string(yaml_str: str) -> WorkflowDefinition:
    """Load and validate a WorkflowDefinition from a YAML string.

    Args:
        yaml_str: Raw YAML content.

    Returns:
        A validated WorkflowDefinition.

    Raises:
        yaml.YAMLError: If the string is not valid YAML.
        pydantic.ValidationError: If the workflow fails validation.
    """
    data: dict[str, Any] = yaml.safe_load(yaml_str)
    return _build_workflow(data)


def list_workflows(directory: Path) -> list[WorkflowDefinition]:
    """Load all non-template YAML workflows from a directory.

    Files whose names start with `_` are treated as templates and skipped.

    Args:
        directory: Directory to scan for .yml files.

    Returns:
        Sorted list of validated WorkflowDefinitions (sorted by file name).
    """
    workflows: list[WorkflowDefinition] = []
    for path in sorted(directory.glob("*.yml")):
        if not path.name.startswith("_"):
            workflows.append(load_workflow(path))
    return workflows
