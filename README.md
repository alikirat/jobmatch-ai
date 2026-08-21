# JobMatch AI

An AI-powered job search assistant that ingests job postings, scores them against your resume, analyzes gaps, and helps optimize your resume content, surfaced through a swipeable review interface.

![JobMatch AI screenshot](docs/screenshot.png)

## Monorepo layout

```
jobmatch-ai/
├── backend/    Python API layer (FastAPI), serves the frontend and orchestrates the agent graph
├── agents/     Python ADK 2.0 graph workflow: ingest → score → gap analysis → optimize
└── frontend/   React app with a swipe-card interface for reviewing matched jobs
```

### backend/

HTTP API built on FastAPI. Talks to MongoDB for persistence and invokes the workflow defined in `agents/`.

### agents/

Google Agent Development Kit (ADK 2.0) graph workflow. Each stage is a node in the graph:

1. **Ingest**: pull in raw job postings
2. **Score**: score fit against a resume
3. **Gap analysis**: identify missing skills/experience
4. **Optimize**: propose resume content changes

### frontend/

React + TypeScript app. Presents scored jobs as swipeable cards for quick accept/reject review.

## Data

MongoDB stores:
- Scored jobs
- Resume versions
- Application tracking state

### Local MongoDB

A local, authenticated MongoDB instance is defined in `docker-compose.yml`.

1. Copy `.env.example` to `.env` and set `MONGO_ROOT_USERNAME` / `MONGO_ROOT_PASSWORD`
   (and update `MONGODB_URI` to match, if you changed them).
2. Start it with:

   ```
   docker compose up -d
   ```

   Data persists across restarts in a named Docker volume. The container only binds to
   `127.0.0.1:27017`, so it isn't reachable from outside the host.
3. The backend reads `MONGODB_URI` / `MONGODB_DATABASE` from the environment (via
   `.env`) to connect.

**Never commit `.env`**. Only `.env.example` (with placeholder values) belongs in git.
`.env` is already listed in `.gitignore`.

## Running locally

Prerequisites: Python 3.11+, [uv](https://github.com/astral-sh/uv), Node.js, Docker.

1. **MongoDB**: see [Local MongoDB](#local-mongodb) above; leave it running.
2. **Backend** (from the repo root):

   ```
   uv venv .venv
   source .venv/bin/activate
   uv pip install -e "./backend[dev]" -e "./agents[dev]"

   cd backend
   PYTHONPATH=..:. uvicorn app.main:app --reload --port 8000
   ```

   `agents` and `backend` are sibling packages, so `PYTHONPATH` needs both the repo
   root (for `agents`) and `backend/` (for `app`). Port **8000** matters: it's what
   the frontend's Vite dev proxy expects.

   Scoring calls a real Gemini model by default (`get_llm_client()` in
   `backend/app/dependencies.py` returns `None`, so nodes fall back to
   `AdkLlmClient`), so `GOOGLE_API_KEY` must be set in `.env`. Gemini occasionally
   returns a transient `503 UNAVAILABLE` under load. Just retry the request.

3. **Frontend** (from `frontend/`):

   ```
   npm install
   npm run dev
   ```

   Opens on `http://localhost:5173` and proxies `/jobs`, `/score`, `/resumes`,
   `/ingest` to the backend on port 8000 (see `frontend/vite.config.ts`).

4. **Get some scored jobs into the queue**: the swipe UI only shows postings with
   `status: "scored"`. Either run `POST /ingest/adzuna` (needs `ADZUNA_APP_ID` /
   `ADZUNA_APP_KEY`), or `POST /score` directly with a resume and a job posting body
   (see `agents/fixtures/` for example shapes). A Remotive job source also exists
   (`agents/ingest/remotive_client.py`), reachable via
   `agents/scripts/run_ingestion_batch.py` rather than its own API route.

Running the test suites doesn't need any of the above except the Python venv.
`agents/tests` and `backend/tests` inject scripted/stub LLM clients and a
`JsonStore`, so they don't touch MongoDB or make real API calls:

```
cd agents && python -m pytest -q
cd backend && PYTHONPATH=..:. python -m pytest -q
```

## Status

Functional end to end: ingest, score, gap analysis, and optimize all work, backed by
MongoDB persistence, a working FastAPI backend, and a React frontend for reviewing
scored jobs (including an expandable detail view with gap analysis and resume
suggestions). Covered by 16 test files across the `agents` and `backend` packages.
No live deployment yet, everything runs locally per the instructions above.
