import pytest
import json
from uuid import uuid4
from datetime import datetime
from clinical_ai_shared.schemas import (
    AgentIdentity,
    ProvenanceRecord,
    ConfidenceScore,
    PaginatedResponse,
    DocumentType,
    DocumentInput,
    ExtractionResult,
    ValidationStatus,
    ValidationResult,
    ValidationFeedback,
    EpisodicEntry,
    LongTermEntry,
    ProceduralTemplate,
    ConsolidationStats,
    MemorySearchResult,
    WorkflowStatus,
    WorkflowState,
    NodeType,
    RetryConfig,
    NotificationConfig,
    NodeDefinition,
    EdgeDefinition,
    StateFieldDefinition,
    WorkflowDefinition,
    NodeResult,
    AuditLogEntry,
    AuditQuery,
    AuditExportRequest,
    InteractionSeverity,
    MedicationInput,
    NormalizedMedication,
    DrugInteraction,
    RiskAssessmentReport,
)

def round_trip(model_class, data):
    instance = model_class(**data)
    json_data = instance.model_dump_json()
    new_instance = model_class.model_validate_json(json_data)
    assert instance == new_instance
    return instance

def test_common_schemas():
    round_trip(AgentIdentity, {"name": "test", "version": "1.0.0"})
    round_trip(ProvenanceRecord, {
        "document_id": uuid4(),
        "page_number": 1,
        "extraction_agent": "test_agent",
        "source_text": "sample"
    })
    round_trip(ConfidenceScore, {"score": 0.9, "reasoning": "test"})
    round_trip(PaginatedResponse[int], {
        "items": [1, 2, 3],
        "total": 3,
        "page": 1,
        "page_size": 10,
        "pages": 1
    })

def test_document_schemas():
    round_trip(DocumentInput, {
        "document_id": uuid4(),
        "filename": "test.pdf",
        "content_type": "application/pdf",
        "phi_sensitive": True,
        "metadata": {"key": "value"}
    })
    round_trip(ExtractionResult, {
        "document_id": uuid4(),
        "document_type": DocumentType.LAB_REPORT,
        "fields": {"a": 1},
        "confidence_scores": {"a": 0.9},
        "provenance": [],
        "model_used": "claude",
        "extracted_at": datetime.now()
    })

def test_validation_schemas():
    round_trip(ValidationResult, {
        "document_id": uuid4(),
        "status": ValidationStatus.PASS,
        "overall_confidence": 0.95,
        "field_results": {"a": True},
        "failures": [],
        "rag_references": [],
        "feedback": "good"
    })
    round_trip(ValidationFeedback, {"field_name": "a", "issue": "none", "suggested_fix": "none"})

def test_memory_schemas():
    round_trip(EpisodicEntry, {
        "session_id": uuid4(),
        "timestamp": datetime.now(),
        "agent": "agent",
        "action": "action",
        "input_summary": "in",
        "output_summary": "out",
        "outcome": "success",
        "confidence": 0.9
    })
    round_trip(LongTermEntry, {
        "entry_id": uuid4(),
        "content": "content",
        "embedding": [0.1, 0.2],
        "importance_score": 0.8,
        "created_at": datetime.now(),
        "last_accessed": datetime.now(),
        "access_count": 5,
        "source_episodes": [uuid4()]
    })
    round_trip(ProceduralTemplate, {
        "template_id": uuid4(),
        "document_type": DocumentType.CLINICAL_NOTE,
        "format_fingerprint": "hash",
        "extraction_hints": {},
        "success_rate": 0.7,
        "last_updated": datetime.now()
    })
    round_trip(ConsolidationStats, {
        "scanned": 10, "deduplicated": 8, "reflected": 5, "promoted": 2, "decayed": 1, "run_at": datetime.now()
    })
    round_trip(MemorySearchResult, {
        "entry_id": uuid4(), "content": "c", "score": 0.5, "metadata": {}
    })

def test_workflow_schemas():
    round_trip(WorkflowState, {
        "run_id": uuid4(),
        "workflow_name": "wf",
        "status": WorkflowStatus.RUNNING,
        "current_node": "node",
        "checkpoint": {},
        "started_at": datetime.now(),
        "updated_at": datetime.now()
    })
    round_trip(WorkflowDefinition, {
        "name": "wf",
        "version": "1",
        "state_schema": [{"name": "s", "type_hint": "str"}],
        "nodes": [{"id": "n", "agent": "a"}],
        "edges": [{"from_node": "n", "to_node": "END"}]
    })
    round_trip(NodeResult, {
        "node_id": "n", "output": {}, "cost_usd": 0.1, "duration_ms": 100, "timestamp": datetime.now()
    })

def test_audit_schemas():
    round_trip(AuditLogEntry, {
        "entry_id": uuid4(),
        "run_id": uuid4(),
        "agent": "a",
        "node": "n",
        "input_hash": "h",
        "output_summary": "o"
    })
    round_trip(AuditQuery, {"run_id": uuid4(), "page": 1})
    round_trip(AuditExportRequest, {"format": "csv"})

def test_pharma_schemas():
    round_trip(MedicationInput, {"name": "m", "dose": "1", "frequency": "1"})
    round_trip(NormalizedMedication, {"rxcui": "1", "name": "n", "standard_name": "s", "confidence": 1.0})
    round_trip(DrugInteraction, {
        "drug_a": "a", "drug_b": "b", "severity": InteractionSeverity.HIGH
    })
    round_trip(RiskAssessmentReport, {
        "report_id": uuid4(), "medications": [], "interactions": [], "summary": "s", "recommendations": []
    })

def test_json_schema():
    # Verify we can get JSON schema (used for Claude tool use)
    schema = ExtractionResult.model_json_schema()
    assert "properties" in schema
    assert schema["title"] == "ExtractionResult"
