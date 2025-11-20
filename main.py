from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()  # Must be first so env is available during imports

from datetime import datetime
from uuid import UUID, uuid4
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Path, Query, Request, Response, Header
from fastapi.middleware.cors import CORSMiddleware

from models.sentiment import TextInput, SentimentResult, SentimentUpdate
from db.sentiment_service import SentimentMySQLService

import os

print(f"DB_HOST={os.environ.get('DB_HOST')}, DB_USER={os.environ.get('DB_USER')}")


app = FastAPI(
    title="Sentiment Analysis Microservice (DB version)",
    description="FastAPI service connected to MySQL via SentimentMySQLService.",
    version="0.3.0",
)

# Optional: allow Swagger or local tools from anywhere; tighten in prod
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],  # set to your frontend origins in prod
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )


def make_result(text: str) -> SentimentResult:
    """Dummy analyzer; will be replaced by Hume.ai client later."""
    return SentimentResult(
        id=uuid4(),
        text=text,
        sentiment="neutral",
        confidence=0.0,
        analyzed_at=datetime.utcnow(),
    )

def compute_etag(sentiment: SentimentResult) -> str:
    """
    Compute a weak ETag for a SentimentResult.

    We use:
      W/"<id>-<unix_timestamp>"
    as the ETag value.

    This is enough to demonstrate correct ETag processing for the assignment.
    """
    # Use integer seconds to keep it stable and readable
    ts = int(sentiment.analyzed_at.timestamp())
    return f'W/"{sentiment.id}-{ts}"'

@app.get("/db_check", tags=["meta"])
def health():
    """
    Simple DB-backed health check.
    """
    try:
        with SentimentMySQLService() as service:
            conn = service.get_connection()
            # quick sanity query
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
            cur.close()
        return {"status": "ok", "db": "connected"}
    except Exception as e:
        return {"status": "degraded", "error": str(e)}


@app.get("/sentiments", response_model=List[SentimentResult], tags=["sentiments"])
def list_sentiments(
    limit: int = Query(100, ge=1, le=1000, description="Max number of rows to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """Retrieve all sentiment records (paginated)."""
    try:
        with SentimentMySQLService() as service:
            results = service.retrieve_all(limit=limit, offset=offset)
            return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")


@app.post("/sentiments", response_model=SentimentResult, status_code=201, tags=["sentiments"])
def create_sentiment(payload: TextInput, response: Response):
    """
    Create a new sentiment record (insert into requests + sentiments).

    Correct 201 Created behavior:
    - status_code = 201
    - Location header points to the newly created resource
    - response body returns the created SentimentResult
    """
    try:
        with SentimentMySQLService() as service:
            # 1. produce initial (dummy) analysis result
            result = make_result(payload.text)

            # 2. persist to DB, service.create returns the joined record (with id, text, ...)
            created = service.create(payload, result)

            # 3. set Location header to the new resource's URL (relative path)
            response.headers["Location"] = f"/sentiments/{created.id}"

            # 4. return the created resource as the response body
            return created

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")


@app.get("/sentiments/{sentiment_id}", response_model=SentimentResult, tags=["sentiments"], responses=
    {
        304: {
            "description": "Not Modified - The resource has not changed since the ETag provided.",
            "content": {
                "application/json": {
                    "example": {"detail": "Not Modified"}
                }
            },
        }
    })
def get_sentiment(
    sentiment_id: UUID = Path(..., description="Sentiment record ID"),
    request: Request = None,
    response: Response = None,
    if_none_match: str | None = Header(default=None, description="ETag value for conditional GET"),
):
    """
    Retrieve one sentiment record by ID (JOIN requests + sentiments).

    ETag behavior:
    - Always computes an ETag based on (id, analyzed_at).
    - If the client sends `If-None-Match` with the same ETag value,
      the server returns 304 Not Modified (no body).
    - Otherwise, it returns 200 OK with the resource and ETag header.
    """
    try:
        with SentimentMySQLService() as service:
            record = service.retrieve(sentiment_id)
            if not record:
                raise HTTPException(status_code=404, detail="Sentiment not found")

        # Compute current ETag for this resource
        current_etag = compute_etag(record)

        # compare with client header
        if if_none_match == current_etag:
            return Response(status_code=304)

        # Otherwise, send the resource and include the ETag header
        response.headers["ETag"] = current_etag
        return record

    except HTTPException:
        # Re-raise HTTPException directly (404, etc.)
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")


@app.put("/sentiments/{sentiment_id}", response_model=SentimentResult, tags=["sentiments"])
def update_sentiment(sentiment_id: UUID, payload: SentimentUpdate):
    """
    Update an existing sentiment record by ID.
    Only 'sentiment', 'confidence', 'analyzed_at' are mutable.
    """
    try:
        with SentimentMySQLService() as service:
            existing = service.retrieve(sentiment_id)
            if not existing:
                raise HTTPException(status_code=404, detail="Sentiment not found")

            merged = existing.model_dump()
            # default analyzed_at to now if user didn't provide it
            update_dict = payload.model_dump(exclude_unset=True)
            if "analyzed_at" not in update_dict:
                update_dict["analyzed_at"] = datetime.utcnow()

            merged.update(update_dict)
            updated = SentimentResult(**merged)

            result = service.update(sentiment_id, updated)
            if not result:
                raise HTTPException(status_code=404, detail="Sentiment not found")
            return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")


@app.delete("/sentiments/{sentiment_id}", status_code=204, tags=["sentiments"])
def delete_sentiment(sentiment_id: UUID):
    """Delete a sentiment and its corresponding request record."""
    try:
        with SentimentMySQLService() as service:
            deleted = service.delete(sentiment_id)
            if not deleted:
                raise HTTPException(status_code=404, detail="Sentiment not found")
            return None
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")


@app.get("/", tags=["meta"])
def root():
    return {"message": "Sentiment Analysis API connected to MySQL. See /docs for UI."}


if __name__ == "__main__":
    import uvicorn
    # In prod, prefer systemd or process manager; this is dev convenience.
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
