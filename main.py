from __future__ import annotations
from dotenv import load_dotenv
load_dotenv()
from datetime import datetime
from uuid import UUID, uuid4
from typing import List

from fastapi import FastAPI, HTTPException, Path

# Local imports
from models.sentiment import TextInput, SentimentResult, SentimentUpdate
from db.sentiment_service import SentimentMySQLService

import os

print(f"DB_HOST={os.environ.get('DB_HOST')}, DB_USER={os.environ.get('DB_USER')}")



# -----------------------------------------------------------------------------
# Initialize app
# -----------------------------------------------------------------------------
app = FastAPI(
    title="Sentiment Analysis Microservice (DB version)",
    description="FastAPI service connected to MySQL via SentimentMySQLService.",
    version="0.2.0",
)


# -----------------------------------------------------------------------------
# Helper function: dummy analyzer (to be replaced by Hume.ai)
# -----------------------------------------------------------------------------
def make_result(text: str) -> SentimentResult:
    """Return a placeholder sentiment result for now."""
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
    """
    Retrieve all sentiment records from MySQL.
    """
    service = SentimentMySQLService()
    try:
        results = service.retrieve_all()
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        service.close_connection()


@app.post("/sentiments", response_model=SentimentResult, status_code=201)
def create_sentiment(payload: TextInput):
    """
    Create a new sentiment record: insert into requests + sentiments tables.
    """
    service = SentimentMySQLService()
    result = make_result(payload.text)
    try:
        print(payload)
        print(result)
        service.create(payload, result)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        service.close_connection()


@app.get("/sentiments/{sentiment_id}", response_model=SentimentResult)
def get_sentiment(sentiment_id: UUID = Path(..., description="Sentiment record ID")):
    """
    Retrieve one sentiment record by ID (JOIN requests + sentiments).
    """
    service = SentimentMySQLService()
    try:
        record = service.retrieve(sentiment_id)
        if not record:
            raise HTTPException(status_code=404, detail="Sentiment not found")
        return record
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        service.close_connection()


@app.put("/sentiments/{sentiment_id}", response_model=SentimentResult)
def update_sentiment(sentiment_id: UUID, payload: SentimentUpdate):
    """
    Update an existing sentiment record by ID.
    """
    service = SentimentMySQLService()

    # 取舊資料
    existing = service.retrieve(sentiment_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Sentiment not found")

    # 合併新資料
    updated_data = existing.model_dump()
    updated_data.update(payload.model_dump(exclude_unset=True))
    updated = SentimentResult(**updated_data)

    try:
        result = service.update(sentiment_id, updated)
        return result
    finally:
        service.close_connection()


@app.delete("/sentiments/{sentiment_id}", status_code=204)
def delete_sentiment(sentiment_id: UUID):
    """
    Delete a sentiment and its corresponding request record.
    """
    service = SentimentMySQLService()
    try:
        deleted = service.delete(sentiment_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Sentiment not found")
        return None
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        service.close_connection()


# -----------------------------------------------------------------------------
# Root
# -----------------------------------------------------------------------------
@app.get("/")
def root():
    """Simple root endpoint."""
    return {"message": "Sentiment Analysis API connected to MySQL. See /docs for UI."}


# -----------------------------------------------------------------------------
# Entrypoint
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
