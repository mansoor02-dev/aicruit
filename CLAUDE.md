# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository layout

This is a polyrepo-in-monorepo for **AIcruit** (a.k.a. "Harvest AI Hire"), an AI-driven recruitment platform. Top-level folders:

`frontend/` — Next.js 14 (App Router, TypeScript, Tailwind + shadcn/ui)

`gateway/` — FastAPI **backend router / API gateway** (the only service the frontend talks to)

`services/` — Independent FastAPI microservices, each with its own Dockerfile, requirements.txt, and `.env`

1. `database/` — `schema.sql` + `init_db.py` (one-shot schema bootstrap container)

`infra/docker/docker-compose.yml` — local dev orchestration for everything except the frontend

`shared/` — currently empty placeholder

## Service map (ports & responsibilities)

The gateway is the single front door; it fans out to microservices over HTTP via `httpx`. Service URLs are injected as env vars (`*_URL`) so the same code runs against Docker hostnames locally and Railway URLs in prod.

| Service                 | Port | Role                                                                   |
| ----------------------- | ---- | ---------------------------------------------------------------------- |
| `frontend`            | 3000 | Next.js UI (calls gateway only)                                        |
| `gateway`             | 8000 | API gateway:`/auth/*` (Cognito), `/job/*`, `/interview/*`        |
| `file-service`        | 8005 | File uploads; serves files at `/static/...` (uploads dir mounted in) |
| `resume-parser`       | 8006 | PDF/DOCX → structured JSON via Gemini or local GGUF model             |
| `transcribe-audio`    | 8007 | Whisper/Groq audio → transcript                                       |
| `question-generation` | 8010 | LLM (OpenRouter) generates next interview question + follow-ups        |
| `text-to-speech`      | 8011 | Piper local TTS (espeak-ng) — synthesizes the question audio          |
| `report-generation`   | 8012 | LLM-powered final interview reports (recruiter + candidate views)      |
| `postgres`            | 5432 | Primary datastore                                                      |
| `pgadmin`             | 5050 | Admin UI (`admin@aicruit.com` / `admin123` in compose)             |

## Architecture: data & control flow

### Auth

- **AWS Cognito** is the source of truth for credentials. `gateway/app/routes/auth.py` calls `cognito-idp` (boto3) for signup/login/OTP/refresh.
- A mirror **users** row is created in Postgres on signup, joined to Cognito via `users.cognito_sub`.
- `core/security.py::get_current_user` does a **soft verify** (decodes JWT claims without JWKS validation — explicitly marked as a 40%-submission shortcut) and looks up the user by `cognito_sub`. Replace with proper JWKS verification before production.
- `RoleChecker(["RECRUITER","ADMIN"])` is the standard FastAPI dependency for route-level RBAC.

### Domain model (see `database/schema.sql`)

The schema models a SaaS ATS:
`companies → recruiters → jobs → applications → interviews → interview_questions / interview_responses / reports / cheating_events`

Notes specific to this codebase:

- `applications` has a `UNIQUE(job_id, candidate_id)` constraint — duplicate apply attempts must be handled.
- AI fields live alongside relational ones: `jobs.required_skills` (JSONB), `applications.ai_match_score`, `interview_responses.ai_score / sentiment`, `reports.category_scores` (JSONB).
- `ai_interview_sessions` + `ai_interview_turns` are a parallel store for the live LLM interview loop, keyed by an 8-char `session_id` (separate from the UUID `interviews.id`).
- Migrations under `database/migrations/*.sql` are **not auto-applied** by `init_db.py` — apply them manually against the running Postgres.

### Gateway models convention

Inside `gateway/app/models/` there are intentionally **two files per entity**:

- `<entity>.py` — Pydantic request/response schemas (e.g. `job.py`, `interview.py`)
- `<entity>_model.py` — SQLAlchemy ORM declarations (e.g. `job_model.py`, `interview_model.py`)

Don't merge these. New entities should follow the same split.

### Interview orchestration (the hot path)

`gateway/app/routes/interview.py` is the longest and most opinionated module. The flow:

1. Recruiter schedules → `interviews` row created (status `scheduled`).
2. Candidate starts → gateway loops up to `MAX_QUESTIONS=10`, with `QUESTIONS_PER_CATEGORY=3` per skill in `jobs.required_skills`.
3. For each turn: gateway calls `question-generation` (with prior Q/A scoped to the **current category only**), then `text-to-speech`, and streams the WAV back with metadata in `X-Interview-*` response headers (frontend reads these — `Access-Control-Expose-Headers` is required).
4. Candidate uploads audio answer → gateway calls `transcribe-audio`, persists `interview_responses`, advances category.
5. Anti-cheat: `ANSWER_TIMEOUT_SECONDS=300` per question; a `hardcoded_resume.json` fallback exists for demos when no resume is parsed yet.
6. On completion → gateway calls `report-generation` and stores into `reports`.

When editing this file, preserve the category-scoped `previous_qa` building (`_get_previous_qa_for_category`) — the question generator is stateless and relies on the gateway for context windowing.

### Frontend ↔ Gateway

- Single base URL: `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`), wired through `frontend/src/lib/api.ts`.
- Tokens stored in `localStorage` under key `aicruit_tokens` as `{ access_token, id_token, refresh_token }`. `getAuthToken()` reads `access_token` and the `apiRequest` helper attaches it as a Bearer header.
- All client-side state lives in React Context (`AuthContext`) + TanStack React Query. There is no Redux. Pages are mostly `'use client'` because they read auth state from `localStorage`.
- Route structure mirrors roles: `src/app/recruiter/{dashboard,job,candidates,interview-details,settings}` and `src/app/candidate/{job,applications,interview,profile}`.

## Running locally

### Full stack (recommended)

```sh
# from repo root
docker compose -f infra/docker/docker-compose.yml up --build
```

This starts Postgres, pgadmin, db-init (runs `schema.sql` then exits), all 6 microservices, and the gateway. The frontend is **not** in compose — run it separately.

The gateway compose service mounts `${USERPROFILE}/.aws:/root/.aws:ro` so boto3 can reach Cognito with your local AWS credentials. On non-Windows hosts, change this to `~/.aws`.

### Frontend

```sh
cd frontend
npm install
npm run dev          # http://localhost:3000
npm run build        # production build
npm run lint         # ESLint (next/core-web-vitals)
```

The repo also ships a `bun.lockb`; `bun install && bun dev` works equivalently.

### Single Python service

Each service is self-contained:

```sh
cd services/<name>
pip install -r requirements.txt
uvicorn app.main:app --reload --port <port>
# resume-parser uses app.api:app; text-to-speech uses main:app (no app/ package)
```

Each has a `.env` (not committed for some) with provider keys: `GEMINI_API_KEY`, `OPENROUTER_API_KEY`, `GROQ_API_KEY`.

### Database

- `schema.sql` is **idempotent** (`CREATE TABLE IF NOT EXISTS`) — re-running `db-init` is safe but won't apply column changes. For schema edits, drop the affected tables or run files in `database/migrations/` manually.
- DB connection is read in this order: `DATABASE_URL` env var, otherwise composed from `DB_USER`/`DB_PASS`/`DB_HOST`/`DB_PORT`/`DB_NAME` (defaults: `admin`/`admin123`/`postgres`/`5432`/`aicruit`).

## Deployment

- **Railway** is the production target. Each service has both a `Dockerfile` and a `nixpacks.toml` + `Procfile`; Railway picks Nixpacks by default. The `Procfile` uses `gunicorn -k uvicorn.workers.UvicornWorker -w 2 -b 0.0.0.0:$PORT`.
- Service-to-service URLs **must** be set per service via env vars on Railway (e.g. `QUESTION_GEN_URL`, `TTS_URL`, `TRANSCRIBE_URL`, `REPORT_GEN_URL`, `FILE_SERVICE_URL`, `RESUME_PARSER_URL`). Defaults in the code point at `localhost` and will not work in prod.
- `FRONTEND_ORIGINS` (comma-separated) controls CORS on every Python service — set this on every deployed service, not just the gateway.

## Conventions worth knowing

- **All Python services are FastAPI + SQLAlchemy** with the same shape: `app/main.py` (or `app/api.py` for resume-parser) wiring CORS + routers; routers/handlers in submodules. Stick to this pattern.
- **`/health` endpoint** exists on every service and is wired into compose healthchecks for the LLM services.
- **No tests** are checked in. There is no test runner configured in any service or in the frontend. If adding tests, you are establishing the convention.
- **Secrets in repo**: `gateway/.env` and several service `.env` files are committed and contain real-looking credentials (Cognito client secret, GROQ key in compose, DB password). Treat any value you find here as already leaked; rotate before shipping anything externally, and do not add new secrets to committed `.env` files.
