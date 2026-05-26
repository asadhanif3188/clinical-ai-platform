from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict
from clinical_ai_shared.schemas.common import ProvenanceRecord, ConfidenceScore

class DocumentType(str, Enum):
    LAB_REPORT = "lab_report"
    CLINICAL_NOTE = "clinical_note"
    TRIAL_SUMMARY = "trial_summary"
    ADVERSE_EVENT = "adverse_event"
    UNKNOWN = "unknown"

class DocumentInput(BaseModel):
    document_id: UUID = Field(..., description="UUID assigned on upload")
    filename: str = Field(..., description="Original filename")
    content_type: str = Field(..., description="MIME type, e.g., 'application/pdf'")
    phi_sensitive: bool = Field(False, description="If True, document contains PHI and must stay local")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional document metadata")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "document_id": "550e8400-e29b-41d4-a716-446655440000",
                "filename": "patient_report.pdf",
                "content_type": "application/pdf",
                "phi_sensitive": True,
                "metadata": {"uploaded_by": "dr_smith"}
            }
        }
    )

class ExtractionResult(BaseModel):
    document_id: UUID
    document_type: DocumentType
    fields: dict[str, Any] = Field(..., description="Type-specific extracted fields")
    confidence_scores: dict[str, float] = Field(..., description="Per-field confidence scores")
    provenance: list[ProvenanceRecord] = Field(..., description="Source location for extracted data")
    model_used: str
    extracted_at: datetime = Field(default_factory=lambda: datetime.now())

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "document_id": "550e8400-e29b-41d4-a716-446655440000",
                "document_type": "lab_report",
                "fields": {"glucose": 95, "unit": "mg/dL"},
                "confidence_scores": {"glucose": 0.99},
                "provenance": [],
                "model_used": "claude-3-haiku",
                "extracted_at": "2026-05-26T10:00:00Z"
            }
        }
    )
