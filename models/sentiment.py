from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4
from pydantic import BaseModel, Field

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

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "text": "The food was okay but the service was slow.",
                "sentiment": "neutral",
                "confidence": 0.63,
                "analyzed_at": "2025-10-16T12:34:56Z",
            }
        }
    }
