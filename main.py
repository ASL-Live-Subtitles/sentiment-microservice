from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()  # Must be first so env is available during imports

from datetime import datetime
from uuid import UUID, uuid4
from typing import List, Optional, Dict

from fastapi import FastAPI, HTTPException, Path, Query, Request, Response, Header, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

from models.sentiment import TextInput, SentimentResult, SentimentUpdate, SentimentLinks, SentimentJobStatus, SentimentJobLinks
from db.sentiment_service import SentimentMySQLService

import os
import time

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

from services.edenai_client import EdenAIClient

sentiment_jobs: Dict[UUID, SentimentJobStatus] = {}
edenai_client = EdenAIClient()

def sentiment_analysis(text: str) -> SentimentResult:
    """Calls Eden AI and converts the result to our local model."""
    best_result = edenai_client.analyze_sentiment(text)
    
    if not best_result:
        # Handle the case where analysis fails or returns no successful provider
        return SentimentResult(
            id=uuid4(),
            text=text,
            sentiment="unknown",
            confidence=0.0,
            analyzed_at=datetime.utcnow(),
        )
    
    return SentimentResult(
        id=uuid4(),
        text=text,
        sentiment=best_result.get("general_sentiment", "unknown").lower(),
        confidence=best_result.get("general_sentiment_rate", 0.0),
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

def attach_links(sentiment: SentimentResult) -> SentimentResult:
    """
    Return a new SentimentResult including hypermedia links
    using relative paths (linked data requirement).
    """
    data = sentiment.model_dump(exclude={"links"})

    return SentimentResult(
        **data,
        links=SentimentLinks(
            self=f"/sentiments/{sentiment.id}",
            collection="/sentiments",
        ),
    )

def attach_job_links(job: SentimentJobStatus) -> SentimentJobStatus:
    """
    Attach hypermedia links (relative paths) to a SentimentJobStatus.

    - links.self   -> /sentiment-async/{job_id}
    - links.result -> /sentiments/{result_id}  (only when completed)
    """
    data = job.model_dump(exclude={"links"})  # avoid double-assignment of 'links'

    links = SentimentJobLinks(
        self=f"/sentiment-async/{job.id}",
        result=f"/sentiments/{job.result_id}" if job.result_id else None,
    )

    return SentimentJobStatus(**data, links=links)

def run_sentiment_job(job_id: UUID, text: str) -> None:
    """
    Background task that:
    1. Updates job status to 'running'
    2. Runs sentiment analysis and writes to DB
    3. Updates job status to 'completed' or 'failed'
    """
    now = datetime.utcnow()

    job = sentiment_jobs.get(job_id)
    if not job:
        return  # Should not happen, but guard anyway

    # --- Simulate real-world delay: queue waiting time (still "pending") ---
    # During this period, GET /sentiment-async/{job_id} will usually see status = "pending"
    time.sleep(5)

    # Mark job as running
    job.status = "running"
    job.updated_at = now
    sentiment_jobs[job_id] = job

    try:
        # --- Simulate processing time while status = "running" ---
        # During this period, polling will usually see status = "running"
        time.sleep(5)

        # Run "real" sentiment creation (same as your sync POST /sentiments)
        result = sentiment_analysis(text)
        with SentimentMySQLService() as service:
            created = service.create(TextInput(text=text), result)

        # Mark job as completed and store result_id
        job.status = "completed"
        job.updated_at = datetime.utcnow()
        job.result_id = created.id
        sentiment_jobs[job_id] = job

    except Exception as e:
        # Mark job as failed
        job.status = "failed"
        job.updated_at = datetime.utcnow()
        job.error_message = str(e)
        sentiment_jobs[job_id] = job

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
        return [attach_links(r) for r in results]
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
            result = sentiment_analysis(payload.text)
            created = service.create(payload, result)

        created = attach_links(created)
        response.headers["Location"] = f"/sentiments/{created.id}"
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
        record_with_links = attach_links(record)
        return record_with_links

    except HTTPException:
        # Re-raise HTTPException directly (404, etc.)
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")


@app.put("/sentiments/{sentiment_id}", response_model=SentimentResult, tags=["sentiments"])
def update_sentiment(sentiment_id: UUID, payload: SentimentUpdate):
    """
    Update the **input text** for an existing sentiment record by ID
    **and** re-run sentiment analysis on the new text.

    Behavior:
    - PUT updates the original text stored in the requests table (requests.input_text).
    - It also re-computes sentiment, confidence and analyzed_at for this record
      using the new text, and returns the updated SentimentResult.
    """
    try:
        if payload.text is None:
            raise HTTPException(status_code=400, detail="No text provided to update")

        with SentimentMySQLService() as service:
            # Re-run sentiment analysis for the new text
            new_result = sentiment_analysis(payload.text)

            # Apply updates to both the request text and sentiment fields
            updated = service.update_with_new_analysis(
                sentiment_id=sentiment_id,
                new_text=payload.text,
                result_data=new_result,
            )
            if not updated:
                raise HTTPException(status_code=404, detail="Sentiment not found")

            # Keep consistent with other endpoints by attaching links
            return attach_links(updated)
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

@app.post(
    "/sentiment-async",
    status_code=202,
    response_model=SentimentJobStatus,
    tags=["async"],
)
def create_async_sentiment(
    payload: TextInput,
    background_tasks: BackgroundTasks,
    response: Response,
):
    """
    Create a sentiment analysis job asynchronously.

    - Returns 202 Accepted (job accepted, not yet finished)
    - Starts a background task to run the actual analysis
    - Sets Location header to /sentiment-async/{job_id}
    - Returns a SentimentJobStatus with status='pending'
    """
    job_id = uuid4()
    now = datetime.utcnow()

    job = SentimentJobStatus(
        id=job_id,
        status="pending",
        created_at=now,
        updated_at=now,
        result_id=None,
        error_message=None,
        links=None,
    )
    sentiment_jobs[job_id] = job

    # Schedule background work
    background_tasks.add_task(run_sentiment_job, job_id, payload.text)

    # Expose relative path to the job resource
    response.headers["Location"] = f"/sentiment-async/{job_id}"

    return attach_job_links(job)

@app.get(
    "/sentiment-async/{job_id}",
    response_model=SentimentJobStatus,
    tags=["async"],
)
def get_async_sentiment_status(
    job_id: UUID = Path(..., description="Sentiment async job ID"),
):
    """
    Poll the status of an asynchronous sentiment analysis job.

    - When status is 'pending' or 'running', result_id will be null.
    - When status is 'completed', result_id will hold the SentimentResult.id.
    - When status is 'failed', error_message may contain more details.
    """
    job = sentiment_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return attach_job_links(job)
