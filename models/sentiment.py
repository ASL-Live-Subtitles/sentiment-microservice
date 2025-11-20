from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4
from pydantic import BaseModel, Field
from typing import Optional

# -------------------------------
# INPUT models
# -------------------------------
class TextInput(BaseModel):
    text: str = Field(
        ...,
        description="The raw text to analyze for sentiment.",
        json_schema_extra={"example": "I absolutely love this product!"}
    )

    model_config = {
        "json_schema_extra": {
            "example": {"text": "The food was okay but the service was slow."}
        }
    }

class SentimentLinks(BaseModel):
    """Hypermedia links related to a sentiment resource."""
    self: str = Field(
        ...,
        description="Relative URL of this sentiment resource.",
        json_schema_extra={"example": "/sentiments/550e8400-e29b-41d4-a716-446655440000"},
    )
    collection: str = Field(
        ...,
        description="Relative URL of the sentiments collection.",
        json_schema_extra={"example": "/sentiments"},
    )
# -------------------------------
# OUTPUT models
# -------------------------------
class SentimentResult(BaseModel):
    id: UUID = Field(
        default_factory=uuid4,
        description="Server-generated analysis ID.",
        json_schema_extra={"example": "550e8400-e29b-41d4-a716-446655440000"},
    )
    text: str = Field(
        ...,
        description="The original text that was analyzed.",
        json_schema_extra={"example": "I absolutely love this product!"},
    )
    sentiment: str = Field(
        ...,
        description="Overall sentiment label (e.g., positive, negative, neutral).",
        json_schema_extra={"example": "positive"},
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score (0.0–1.0) of the sentiment classification.",
        json_schema_extra={"example": 0.95},
    )
    analyzed_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp (UTC) when the analysis was performed.",
        json_schema_extra={"example": "2025-10-16T12:34:56Z"},
    )
    links: Optional[SentimentLinks] = Field(
        default=None,
        description="Hypermedia links (relative paths) for this sentiment resource.",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "text": "The food was okay but the service was slow.",
                "sentiment": "neutral",
                "confidence": 0.63,
                "analyzed_at": "2025-10-16T12:34:56Z",
                "links": {
                    "self": "/sentiments/550e8400-e29b-41d4-a716-446655440000",
                    "collection": "/sentiments"
                }
            }
        }
    }


class SentimentUpdate(BaseModel):
    sentiment: Optional[str] = Field(None, description="Updated sentiment label")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    analyzed_at: Optional[datetime] = Field(None, description="Updated timestamp (UTC)")

# -------------------------------
# ASYNC JOB MODELS
# -------------------------------

class SentimentJobLinks(BaseModel):
    """Hypermedia links for a sentiment async job."""
    self: str = Field(
        ...,
        description="Relative URL of this job resource.",
        json_schema_extra={"example": "/sentiment-async/0c5b0a39-b9b8-4afd-9cc5-e277166a5222"},
    )
    result: Optional[str] = Field(
        default=None,
        description="Relative URL of the final SentimentResult, if the job has completed.",
        json_schema_extra={"example": "/sentiments/960804b6-97cb-413e-83e1-c8207e453a4f"},
    )


class SentimentJobStatus(BaseModel):
    """
    Represents the status of an asynchronous sentiment analysis job.

    This is used by:
    - POST /sentiment-async       (returns 202 Accepted + initial job state)
    - GET  /sentiment-async/{id}  (polling endpoint for job status)
    """
    id: UUID = Field(
        ...,
        description="Async job ID.",
        json_schema_extra={"example": "0c5b0a39-b9b8-4afd-9cc5-e277166a5222"},
    )
    status: str = Field(
        ...,
        description="Job status: pending | running | completed | failed",
        json_schema_extra={"example": "running"},
    )
    created_at: datetime = Field(
        ...,
        description="Job creation timestamp (UTC).",
        json_schema_extra={"example": "2025-10-16T12:00:00Z"},
    )
    updated_at: datetime = Field(
        ...,
        description="Last status update (UTC).",
        json_schema_extra={"example": "2025-10-16T12:00:01Z"},
    )
    result_id: Optional[UUID] = Field(
        default=None,
        description="ID of the created SentimentResult (when status == completed).",
        json_schema_extra={"example": "960804b6-97cb-413e-83e1-c8207e453a4f"},
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Error message if status == failed.",
        json_schema_extra={"example": "Database connection timeout"},
    )
    links: Optional[SentimentJobLinks] = Field(
        default=None,
        description="Hypermedia links (relative paths) to this job and the final sentiment resource.",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "0c5b0a39-b9b8-4afd-9cc5-e277166a5222",
                "status": "completed",
                "created_at": "2025-10-16T12:00:00Z",
                "updated_at": "2025-10-16T12:00:05Z",
                "result_id": "960804b6-97cb-413e-83e1-c8207e453a4f",
                "error_message": None,
                "links": {
                    "self": "/sentiment-async/0c5b0a39-b9b8-4afd-9cc5-e277166a5222",
                    "result": "/sentiments/960804b6-97cb-413e-83e1-c8207e453a4f"
                }
            }
        }
    }
