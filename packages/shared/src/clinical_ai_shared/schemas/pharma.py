from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class InteractionSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MODERATE = "MODERATE"
    LOW = "LOW"


class MedicationInput(BaseModel):
    name: str
    dose: str | None = None
    frequency: str | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"name": "Warfarin", "dose": "5mg", "frequency": "Once daily"}
        }
    )


class NormalizedMedication(BaseModel):
    rxcui: str | None = None
    name: str
    standard_name: str
    confidence: float = Field(..., ge=0.0, le=1.0)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "rxcui": "11289",
                "name": "Warfarin",
                "standard_name": "warfarin",
                "confidence": 1.0,
            }
        }
    )


class DrugInteraction(BaseModel):
    drug_a: str
    drug_b: str
    severity: InteractionSeverity
    mechanism: str | None = None
    clinical_significance: str | None = None
    source_url: str | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "drug_a": "Warfarin",
                "drug_b": "Aspirin",
                "severity": "HIGH",
                "mechanism": "Increased risk of bleeding",
                "clinical_significance": "Use with caution",
                "source_url": "https://api.fda.gov/...",
            }
        }
    )


class RiskAssessmentReport(BaseModel):
    report_id: UUID
    medications: list[NormalizedMedication]
    interactions: list[DrugInteraction]
    summary: str
    recommendations: list[str]
    generated_at: datetime = Field(default_factory=datetime.now)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "report_id": "550e8400-e29b-41d4-a716-446655440004",
                "medications": [],
                "interactions": [],
                "summary": "No critical interactions found",
                "recommendations": ["Continue as prescribed"],
                "generated_at": "2026-05-26T10:00:00Z",
            }
        }
    )
