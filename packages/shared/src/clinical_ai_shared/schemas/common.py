from datetime import datetime
from typing import Generic, TypeVar, Optional, Any
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict

T = TypeVar("T")

class AgentIdentity(BaseModel):
    name: str = Field(..., description="Name of the agent")
    version: str = Field(..., description="Version of the agent")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "intake_agent",
                "version": "1.0.0"
            }
        }
    )

class ProvenanceRecord(BaseModel):
    document_id: UUID = Field(..., description="ID of the source document")
    page_number: Optional[int] = Field(None, description="Page number where data was found")
    extraction_agent: str = Field(..., description="Name of the agent that performed the extraction")
    source_text: Optional[str] = Field(None, description="Original text snippet from the document")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "document_id": "550e8400-e29b-41d4-a716-446655440000",
                "page_number": 1,
                "extraction_agent": "lab_report_agent",
                "source_text": "Glucose: 95 mg/dL"
            }
        }
    )

class ConfidenceScore(BaseModel):
    score: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")
    reasoning: Optional[str] = Field(None, description="Explanation for the confidence score")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "score": 0.95,
                "reasoning": "Standard lab result format recognized with high clarity"
            }
        }
    )

class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [],
                "total": 0,
                "page": 1,
                "page_size": 20,
                "pages": 0
            }
        }
    )
