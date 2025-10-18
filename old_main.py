from __future__ import annotations

from datetime import datetime
from typing import Dict, List
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Path

from models.sentiment import TextInput, SentimentResult


# -----------------------------------------------------------------------------
# App
# -----------------------------------------------------------------------------
app = FastAPI(
    title="Sentiment Analysis Microservice",
    description="Minimal API-first skeleton with in-memory storage.",
    version="0.1.0",
)

# -----------------------------------------------------------------------------
# In-memory store (fake DB)
# -----------------------------------------------------------------------------
# Key: sentiment UUID; Value: SentimentResult
sentiments: Dict[UUID, SentimentResult] = {}


def make_result(text: str) -> SentimentResult:
    """Create a placeholder sentiment result (to be replaced by real model/Hume)."""
    return SentimentResult(
        id=uuid4(),
        text=text,
        sentiment="neutral",
        confidence=0.0,
        analyzed_at=datetime.utcnow(),
    )


# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------
@app.get("/sentiments", response_model=List[SentimentResult])
def list_sentiments():
    """Return all sentiment results."""
    return list(sentiments.values())


@app.post("/sentiments", response_model=SentimentResult, status_code=201)
def create_sentiment(payload: TextInput):
    """Create a new sentiment result from input text."""
    result = make_result(payload.text)
    sentiments[result.id] = result
    return result


@app.get("/sentiments/{sentiment_id}", response_model=SentimentResult)
def get_sentiment(
    sentiment_id: UUID = Path(..., description="Sentiment result ID.")
):
    """Return a single sentiment result by ID."""
    item = sentiments.get(sentiment_id)
    if not item:
        raise HTTPException(status_code=404, detail="Sentiment not found")
    return item


@app.put("/sentiments/{sentiment_id}", response_model=SentimentResult)
def put_sentiment(
    sentiment_id: UUID,
    payload: TextInput,
):
    """
    Replace an existing sentiment result with a new one generated from input text.
    Keeps the same ID to mimic full replacement semantics.
    """
    if sentiment_id not in sentiments:
        raise HTTPException(status_code=404, detail="Sentiment not found")
    updated = make_result(payload.text)
    updated.id = sentiment_id  # preserve ID for PUT semantics
    sentiments[sentiment_id] = updated
    return updated


@app.delete("/sentiments/{sentiment_id}", status_code=204)
def delete_sentiment(sentiment_id: UUID):
    """Delete a sentiment result by ID."""
    if sentiment_id not in sentiments:
        raise HTTPException(status_code=404, detail="Sentiment not found")
    del sentiments[sentiment_id]
    return None


# -----------------------------------------------------------------------------
# Root
# -----------------------------------------------------------------------------
@app.get("/")
def root():
    """Simple health/info endpoint."""
    return {"message": "Sentiment API ready. See /docs for OpenAPI UI."}


# -----------------------------------------------------------------------------
# Entrypoint
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
