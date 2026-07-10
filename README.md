# JobMatch AI

An AI-powered job search assistant that ingests job postings, scores them against your resume, analyzes gaps, and helps optimize your resume content — surfaced through a swipeable review interface.

## Monorepo layout

```
jobmatch-ai/
├── backend/    Python API layer (FastAPI) — serves the frontend and orchestrates the agent graph
├── agents/     Python ADK 2.0 graph workflow: ingest → score → gap analysis → optimize
└── frontend/   React app with a swipe-card interface for reviewing matched jobs
```

### backend/

HTTP API built on FastAPI. Talks to MongoDB for persistence and invokes the workflow defined in `agents/`.

### agents/

Google Agent Development Kit (ADK 2.0) graph workflow. Each stage is a node in the graph:

1. **Ingest** — pull in raw job postings
2. **Score** — score fit against a resume
3. **Gap analysis** — identify missing skills/experience
4. **Optimize** — propose resume content changes

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

**Never commit `.env`** — only `.env.example` (with placeholder values) belongs in git.
`.env` is already listed in `.gitignore`.

## Status

Early scaffolding — no business logic implemented yet.
