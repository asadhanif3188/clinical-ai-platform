from enum import Enum
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict

class ValidationStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    HUMAN_REVIEW = "human_review"

class ValidationResult(BaseModel):
    document_id: UUID
    status: ValidationStatus
    overall_confidence: float = Field(..., ge=0.0, le=1.0)
    field_results: dict[str, bool] = Field(..., description="Pass/fail status per field")
    failures: list[str] = Field(default_factory=list, description="Specific failure reasons")
    rag_references: list[str] = Field(default_factory=list, description="References used for cross-validation")
    feedback: Optional[str] = Field(None, description="Feedback to extraction agent on retry")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "document_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "pass",
                "overall_confidence": 0.98,
                "field_results": {"glucose": True},
                "failures": [],
                "rag_references": ["Clinical Guidelines v2.1"],
                "feedback": None
            }
        }
    )

class ValidationFeedback(BaseModel):
    field_name: str
    issue: str
    suggested_fix: Optional[str] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "field_name": "glucose",
                "issue": "Value out of plausible range",
                "suggested_fix": "Re-extract from page 1"
            }
        }
    )
