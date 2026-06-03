"""Unit tests for the ClinFlow YAML workflow definition parser."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from clinical_ai_clinflow.definitions import (
    EdgeDefinition,
    NodeDefinition,
    RetryConfig,
    StateFieldDefinition,
    WorkflowDefinition,
)
from clinical_ai_clinflow.loader import (
    list_workflows,
    load_workflow,
    load_workflow_from_string,
)

# ---------------------------------------------------------------------------
# Shared YAML fixtures
# ---------------------------------------------------------------------------

VALID_WORKFLOW_YAML = """\
name: test_workflow
version: "1.0"
description: "A minimal valid workflow for testing"

state_schema:
  input_data: str
  result: str | null

nodes:
  - id: process
    agent: process_agent
    timeout_seconds: 30
    retry:
      max_attempts: 2
      backoff_seconds: 5

  - id: validate
    agent: validation_agent

edges:
  - from: process
    to: validate

  - from: validate
    to: END
"""

TEMPLATE_YAML_PATH = (
    Path(__file__).parent.parent.parent
    / "packages"
    / "clinflow"
    / "src"
    / "clinical_ai_clinflow"
    / "workflows"
    / "_template.yml"
)


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


def test_valid_yaml_parses_correctly() -> None:
    wf = load_workflow_from_string(VALID_WORKFLOW_YAML)

    assert wf.name == "test_workflow"
    assert wf.version == "1.0"
    assert wf.description == "A minimal valid workflow for testing"

    assert len(wf.state_schema) == 2
    assert wf.state_schema[0].name == "input_data"
    assert wf.state_schema[0].type_hint == "str"
    assert not wf.state_schema[0].nullable  # "str" has no "null"
    assert wf.state_schema[1].name == "result"
    assert wf.state_schema[1].nullable  # "str | null" contains "null"

    assert len(wf.nodes) == 2
    process_node = next(n for n in wf.nodes if n.id == "process")
    assert process_node.agent == "process_agent"
    assert process_node.timeout_seconds == 30
    assert process_node.retry is not None
    assert process_node.retry.max_attempts == 2

    assert len(wf.edges) == 2
    first_edge = wf.edges[0]
    assert first_edge.from_node == "process"
    assert first_edge.to_node == "validate"
    assert first_edge.condition is None


def test_template_yaml_parses_without_error() -> None:
    """The bundled _template.yml must parse successfully (smoke test)."""
    assert TEMPLATE_YAML_PATH.exists(), f"Template not found at {TEMPLATE_YAML_PATH}"
    wf = load_workflow(TEMPLATE_YAML_PATH)
    assert wf.name == "example_workflow"
    assert len(wf.nodes) == 5
    assert len(wf.edges) == 7


def test_human_gateway_node_parsed() -> None:
    yaml_str = """\
name: hitl_workflow
version: "1.0"

state_schema:
  input: str

nodes:
  - id: extract
    agent: extraction_agent

  - id: review
    type: human_gateway
    assignee_role: clinical_reviewer
    notification:
      channel: slack
      message: "Needs review"

  - id: report
    agent: report_agent

edges:
  - from: extract
    to: review
  - from: review
    to: report
    condition: "approved"
"""
    wf = load_workflow_from_string(yaml_str)
    review_node = next(n for n in wf.nodes if n.id == "review")
    assert review_node.type == "human_gateway"
    assert review_node.agent is None
    assert review_node.assignee_role == "clinical_reviewer"
    assert review_node.notification is not None
    assert review_node.notification.channel == "slack"


def test_conditional_edge_parsed() -> None:
    yaml_str = """\
name: conditional_workflow
version: "1.0"

state_schema:
  status: str

nodes:
  - id: validate
    agent: validator
  - id: pass_node
    agent: pass_agent
  - id: fail_node
    agent: fail_agent

edges:
  - from: validate
    to: pass_node
    condition: "state['status'] == 'PASS'"
  - from: validate
    to: fail_node
    condition: "state['status'] == 'FAIL'"
"""
    wf = load_workflow_from_string(yaml_str)
    assert len(wf.edges) == 2
    assert wf.edges[0].condition == "state['status'] == 'PASS'"
    assert wf.edges[1].condition == "state['status'] == 'FAIL'"


def test_list_workflows_skips_templates(tmp_path: Path) -> None:
    """list_workflows should ignore files starting with underscore."""
    (tmp_path / "_template.yml").write_text(VALID_WORKFLOW_YAML)
    (tmp_path / "real_workflow.yml").write_text(
        VALID_WORKFLOW_YAML.replace("test_workflow", "real_workflow")
    )

    results = list_workflows(tmp_path)
    assert len(results) == 1
    assert results[0].name == "real_workflow"


def test_list_workflows_empty_dir(tmp_path: Path) -> None:
    assert list_workflows(tmp_path) == []


# ---------------------------------------------------------------------------
# Pydantic model construction tests
# ---------------------------------------------------------------------------


def test_retry_config_defaults() -> None:
    r = RetryConfig()
    assert r.max_attempts == 3
    assert r.backoff_seconds == 5


def test_state_field_definition() -> None:
    f = StateFieldDefinition(name="doc_id", type_hint="str", nullable=False)
    assert f.name == "doc_id"
    assert not f.nullable


def test_edge_definition_defaults() -> None:
    e = EdgeDefinition(from_node="a", to_node="b")
    assert e.condition is None
    assert e.max_loops == 3


# ---------------------------------------------------------------------------
# Validation error tests
# ---------------------------------------------------------------------------


def test_missing_required_field_raises_validation_error() -> None:
    """Workflow without `version` must raise ValidationError."""
    yaml_str = """\
name: bad_workflow
state_schema:
  input: str

nodes:
  - id: process
    agent: process_agent

edges:
  - from: process
    to: END
"""
    with pytest.raises(ValidationError):
        load_workflow_from_string(yaml_str)


def test_dangling_to_node_raises_validation_error() -> None:
    """Edge pointing to a non-existent node must raise ValidationError."""
    yaml_str = """\
name: dangling_workflow
version: "1.0"
state_schema:
  input: str

nodes:
  - id: node_a
    agent: agent_a

edges:
  - from: node_a
    to: ghost_node
"""
    with pytest.raises(ValidationError, match="ghost_node"):
        load_workflow_from_string(yaml_str)


def test_dangling_from_node_raises_validation_error() -> None:
    """Edge originating from a non-existent node must raise ValidationError."""
    yaml_str = """\
name: dangling_from_workflow
version: "1.0"
state_schema:
  input: str

nodes:
  - id: node_a
    agent: agent_a

edges:
  - from: ghost_node
    to: node_a
"""
    with pytest.raises(ValidationError, match="ghost_node"):
        load_workflow_from_string(yaml_str)


def test_circular_dependency_raises_validation_error() -> None:
    """A workflow where every node has an outgoing edge (no terminal) must fail.

    A pure cycle — A → B → A — has no terminal node and would run forever.
    The `validate_terminal_nodes` validator catches this.
    """
    yaml_str = """\
name: circular_workflow
version: "1.0"
state_schema:
  input: str

nodes:
  - id: node_a
    agent: agent_a
  - id: node_b
    agent: agent_b

edges:
  - from: node_a
    to: node_b
  - from: node_b
    to: node_a
"""
    with pytest.raises(ValidationError, match="no terminal nodes"):
        load_workflow_from_string(yaml_str)


def test_agent_node_without_agent_field_raises_validation_error() -> None:
    """An 'agent' type node that omits the `agent` field must fail."""
    yaml_str = """\
name: missing_agent_workflow
version: "1.0"
state_schema:
  input: str

nodes:
  - id: process
    type: agent

edges:
  - from: process
    to: END
"""
    with pytest.raises(ValidationError, match="missing required 'agent' field"):
        load_workflow_from_string(yaml_str)


def test_workflow_with_no_nodes_raises_validation_error() -> None:
    yaml_str = """\
name: empty_workflow
version: "1.0"
state_schema:
  input: str
nodes: []
edges: []
"""
    with pytest.raises(ValidationError):
        load_workflow_from_string(yaml_str)


def test_load_workflow_from_file(tmp_path: Path) -> None:
    """load_workflow() from a file path returns the same result as from a string."""
    yml_path = tmp_path / "workflow.yml"
    yml_path.write_text(VALID_WORKFLOW_YAML, encoding="utf-8")

    wf = load_workflow(yml_path)
    assert wf.name == "test_workflow"
    assert len(wf.nodes) == 2
