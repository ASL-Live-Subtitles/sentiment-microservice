# Sentiment Analysis Microservice

## Overview
This is a FastAPI-based microservice for sentiment analysis.
Currently, the service defines API routes and models annotated for OpenAPI generation.
Future versions will integrate with the Hume.ai Emotion API.

## Quick Start

### Prerequisites

- Python 3.11 or higher
- pip or uv package manager

### Installation

1. **Clone the repository:**

```bash
git git@github.com:ASL-Live-Subtitles/sentiment-microservice.git
cd sentiment-microservice
```

2. **Install dependencies:**

```bash
pip install -r requirements.txt
```

3. **Configure environment variables**
create .env file
```bash
DB_HOST=34.xx.xx.xx
DB_USER=sentiment_user
DB_PASSWORD=xxxx
DB_NAME=sentiment_detection

EDENAI_API_KEY = "EDENAI_API_KEY"
```


### Running the Service

**Start the development server:**

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The service will be available at:

- **API Base URL:** http://localhost:8000
- **Interactive API Documentation:** http://localhost:8000/docs

## API Endpoints

### Core Resources

#### Sentiments

- `GET /sentiments` — List all sentiment records (supports limit, offset, ETag, Linked Data)
- `POST /sentiments` — Create a new sentiment record (201 Created, Location header, returns full resource)
- `GET /sentiments/{sentiment_id}` — Retrieve a single sentiment (ETag, 304 Not Modified, Linked Data)
- `PUT /sentiments/{sentiment_id}` — Update an existing sentiment result
- `DELETE /sentiments/{sentiment_id}` — Delete a sentiment + associated request (204 No Content)


#### Asynchronous Sentiment Tasks

- `POST /sentiments-async` — Submit text for async sentiment analysis (202 Accepted, returns task_id, includes Location)
- `GET /sentiments-async/{task_id}/status` — Poll async task status

## Testing the API

### Using Swagger UI (Recommended)

1. **Start the server** (see Running the Service section above)
2. **Open your browser** and navigate to http://localhost:8000/docs
3. **Explore the interactive documentation** - you can test all endpoints directly from the browser

![Swagger UI](/sample_image/SwaggerUI.png)

### Using curl or HTTP clients

**Example: Submit gesture data**

```bash
curl -X 'POST' \
  'http://127.0.0.1:8000/sentiments' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "text": "The food was okay but the service was slow."
}'
```

**Example: List all gestures**

```bash
curl -X 'GET' \
  'http://127.0.0.1:8000/sentiments?limit=100&offset=0' \
  -H 'accept: application/json'
```

## Data Models

### TextInput

```json
{
  "text": "I love this product!"
}
```

### SentimentResult

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "text": "I love this product!",
  "sentiment": "positive, negative, neutral",
  "confidence": 0.93,
  "analyzed_at": "2025-11-15T22:01:36",
  "links": {
    "self": "/sentiments/550e8400-e29b-41d4-a716-446655440000",
    "request": "/requests/550e8400-e29b-41d4-a716-446655440000"
  }
}
```

### SentimentUpdate (PATCH/PUT)

```json
{
  "sentiment": "negative",
  "confidence": 0.12
}
```

## Development

### Project Structure

```
sentiment-service/
│── main.py # FastAPI app + routes
│── models/
│ └── sentiment.py # TextInput, SentimentResult, SentimentUpdate
│── db/
│ ├── abstract_base.py # MySQL connection manager (context manager)
│ └── sentiment_service.py # CRUD implementation
│── .env # DB credentials
│── requirements.txt
└── README.md
```