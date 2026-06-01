# Consumer Sentiment AI App

This project implements the take-home assignment in Python (FastAPI) + React.

## What is implemented

- `POST /jobs` uploads a PDF and immediately returns a `job_id`.
- Asynchronous processing with a background worker pool (3 workers).
- Persistent job/result storage in SQLite.
- `GET /jobs/{id}` returns `queued | running | completed | failed`.
- `GET /jobs/{id}/result` returns structured analysis for completed jobs.
- React UI for upload, status tracking, and result rendering.
- Tests for valid upload, invalid input, job lifecycle, multiple jobs, mocked LLM success, and mocked LLM failure.

## Backend setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY="your_key_here"
uvicorn app.main:app --reload
```

Backend runs on `http://localhost:8000`.

## Frontend setup

```bash
cd frontend
npm install
npm run dev
```

Frontend runs on `http://localhost:5173`.

If needed, set `VITE_API_BASE_URL` in `frontend/.env`:

```bash
VITE_API_BASE_URL=http://localhost:8000
```

## Run tests

```bash
cd backend
pytest
```
