from __future__ import annotations

from datetime import datetime
from typing import Dict, List
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Query, Path

from models.sentiment import TextInput, SentimentResult

# -----------------------------------------------------------------------------
# Initialize FastAPI app
# -----------------------------------------------------------------------------
app = FastAPI(
    title="Sentiment Analysis Microservice",
    description="A simple FastAPI microservice skeleton for sentiment analysis.",
    version="0.1.0",
)

# -----------------------------------------------------------------------------
# In-memory "database"
# -----------------------------------------------------------------------------
# This dictionary will temporarily store SentimentResult objects keyed by their UUID.
sentiments: Dict[UUID, SentimentResult] = {}

# -----------------------------------------------------------------------------
# Helper function (for later use)
# -----------------------------------------------------------------------------
def make_dummy_result(text: str) -> SentimentResult:
    """
    Create a placeholder SentimentResult for demonstration.
    In the future, this will be replaced with a real call to Hume.ai API.
    """
    return SentimentResult(
        id=uuid4(),
        text=text,
        sentiment="neutral",
        confidence=0.0,
        analyzed_at=datetime.utcnow()
    )

# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------

@app.get("/sentiments", response_model=List[SentimentResult])
def list_sentiments():
    """
    Retrieve all sentiment analysis results.
    Currently returns a NOT IMPLEMENTED message.
    """
    return list(sentiments.values())


@app.post("/sentiments", response_model=SentimentResult, status_code=201)
def create_sentiment(input_data: TextInput):
    """
    Submit a new text for sentiment analysis.
    For now, it returns a dummy result (neutral sentiment).
    """
    # In the future: call Hume.ai API here and store the result.
    result = make_dummy_result(input_data.text)
    sentiments[result.id] = result
    return result


@app.get("/sentiments/{sentiment_id}", response_model=SentimentResult)
def get_sentiment(sentiment_id: UUID = Path(..., description="The UUID of the sentiment record to retrieve.")):
    """
    Retrieve a single sentiment analysis result by its ID.
    """
    sentiment = sentiments.get(sentiment_id)
    if not sentiment:
        raise HTTPException(status_code=404, detail="Sentiment not found")
    return sentiment


@app.put("/sentiments/{sentiment_id}", response_model=SentimentResult)
def update_sentiment(sentiment_id: UUID, new_data: SentimentResult):
    """
    Replace an existing sentiment record with new data (full replacement).
    Currently returns NOT IMPLEMENTED.
    """
    if sentiment_id not in sentiments:
        raise HTTPException(status_code=404, detail="Sentiment not found")

    updated = make_dummy_result(new_data.text)
    # Keep the same ID to mimic full replacement behavior
    updated.id = sentiment_id
    sentiments[sentiment_id] = updated
    return updated


@app.delete("/sentiments/{sentiment_id}", status_code=204)
def delete_sentiment(sentiment_id: UUID):
    """
    Delete a sentiment analysis record by its ID.
    """
    if sentiment_id not in sentiments:
        raise HTTPException(status_code=404, detail="Sentiment not found")
    del sentiments[sentiment_id]
    return None


# -----------------------------------------------------------------------------
# Root route
# -----------------------------------------------------------------------------
@app.get("/")
def root():
    """Simple root endpoint."""
    return {"message": "Welcome to the Sentiment Analysis API. See /docs for documentation."}


# -----------------------------------------------------------------------------
# Entrypoint
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    # Run the FastAPI app using uvicorn server
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
