# AIcruit — Code Quality Report

Generated: 2026-04-27
Scope: `frontend/`, `gateway/`, `services/*` (excluding generated/cache/node_modules)

## Tools used

| Layer    | Tool                    | Version | Command                                 |
| -------- | ----------------------- | ------- | --------------------------------------- |
| Frontend | ESLint (next/lint)      | 8.57    | `npm run lint`                        |
| Frontend | TypeScript compiler     | 5.8.3   | `npx tsc --noEmit`                    |
| Backend  | Ruff (lint, complexity) | 0.15.12 | `ruff check ... --select E,F,W,B,C,I` |
| Backend  | Bandit (SAST)           | 1.9.4   | `bandit -r ... -l`                    |

LOC scanned: **~9.96k** TypeScript/TSX, **~5.0k** Python.

---

## 1. Headline numbers

| Category                          | Count | Severity |
| --------------------------------- | ----: | -------- |
| ESLint errors (frontend)          |     5 | Error    |
| ESLint warnings (frontend)        |     1 | Warning  |
| TypeScript compile errors         |     1 | Error    |
| Ruff issues (Python)              |   442 | Mixed    |
| Bandit issues — Medium           |     2 | Medium   |
| Bandit issues — Low              |    12 | Low      |
| Functions over CC=10 (cyclomatic) |     3 | High     |

No High-severity SAST findings. The two Medium findings and three over-complexity functions are the items most worth fixing first.

---

## 2. Frontend (Next.js / TypeScript)

### 2.1 ESLint (`next lint`)

| File                                                  | Line:Col | Rule                            | Severity |
| ----------------------------------------------------- | -------- | ------------------------------- | -------- |
| `src/app/candidate/applications/page.tsx`           | 121:64   | `react/no-unescaped-entities` | Error    |
| `src/app/otp/page.tsx`                              | 137:15   | `react/no-unescaped-entities` | Error    |
| `src/app/otp/page.tsx`                              | 180:21   | `react/no-unescaped-entities` | Error    |
| `src/app/recruiter/dashboard/page.tsx`              | 83:74    | `react/no-unescaped-entities` | Error    |
| `src/app/recruiter/interview-details/[id]/page.tsx` | 177:67   | `react/no-unescaped-entities` | Error    |
| `src/app/recruiter/job/page.tsx`                    | 128:6    | `react-hooks/exhaustive-deps` | Warning  |

All errors are cosmetic (unescaped `'` in JSX). The warning is more meaningful: `fetchJobs` is missing from a `useEffect` dep array, which can cause stale closures.

### 2.2 TypeScript (`tsc --noEmit`)

```
src/lib/api.ts(39,13): error TS2339: Property 'Authorization' does not exist on
  type 'HeadersInit'. Property 'Authorization' does not exist on
  type '[string, string][]'.
```

`HeadersInit` is a union (`Headers | string[][] | Record<string,string>`); narrow to `Record<string,string>` (or use the `Headers` API) to fix.

```ts
// In src/lib/api.ts
const headers: Record<string, string> = {
  'Content-Type': 'application/json',
  ...(options.headers as Record<string, string>),
};
```

### 2.3 Other observations

- **No tests configured.** `package.json` has no `test` script and no test runner is installed. There is no Playwright/Jest/Vitest config in the tree.
- **Auth lives in `localStorage`.** `getAuthToken()` reads `aicruit_tokens.access_token` directly — no refresh-token rotation logic was found. Worth wrapping in a single `useAuth` hook + a fetch interceptor that handles 401 → refresh.
- **shadcn/ui sprawl.** 50+ components under `src/components/ui/` are all referenced — no unused-component warnings — but consider tree-shaking review at build time.

---

## 3. Backend (Python / FastAPI)

### 3.1 Ruff — issue distribution

```
171  E501   line-too-long                       (style)
 84  W293   blank-line-with-whitespace          (style, autofix)
 45  I001   unsorted-imports                    (style, autofix)
 38  B008   function-call-in-default-argument   (BUG-PRONE)
 29  B904   raise-without-from-inside-except    (debuggability)
 25  W292   missing-newline-at-end-of-file      (style, autofix)
 22  F401   unused-import                       (autofix)
 10  W191   tab-indentation                     (style)
  7  F841   unused-variable
  7  W291   trailing-whitespace
  3  C901   complex-structure                   (HIGH PRIORITY)
  1  E402   module-import-not-at-top-of-file
```

**183 of 442 issues are auto-fixable** (`ruff check --fix`). Recommend running this after a clean commit so the diff is reviewable.

#### Notable categories

- **`B008` — Mutable / function-call defaults (38 occurrences).** Most of these are **intentional FastAPI patterns** (`Depends(...)`, `File(...)`, `Form(...)`, `Body(...)`). Configure Ruff to ignore them:
  ```toml
  # pyproject.toml or ruff.toml
  [tool.ruff.lint.flake8-bugbear]
  extend-immutable-calls = ["fastapi.Depends", "fastapi.File", "fastapi.Form", "fastapi.Body", "fastapi.Query"]
  ```
- **`B904` — Raise without `from` (29).** Every `except Exception as e: raise HTTPException(...)` in the codebase loses the original traceback. Use `raise HTTPException(...) from e` so debugging in prod works.
- **`F401` / `F841` — Dead code (29 total).** Trivially removable. Includes `from datetime import timedelta` in `gateway/app/routes/interview.py:4` and an unused `llm = LLMLoader(...)` assignment in `services/question-generation/app/main.py:39` (the `LLMLoader` is constructed and immediately thrown away — likely a real bug).

### 3.2 Cyclomatic complexity (C901, threshold = 10)

| Function                    | File                                     | CC |
| --------------------------- | ---------------------------------------- | -- |
| `upload_and_parse_resume` | `gateway/app/routes/job.py:183`        | 20 |
| `evaluate_and_generate`   | `gateway/app/routes/interview.py:473`  | 16 |
| `parse_resume_by_id`      | `services/resume-parser/app/api.py:92` | 15 |

These three functions concentrate the system's risk. Each does ingest → external HTTP call → parse → DB write inside one giant try/except. They should each be split into ~3 helpers (validate, fetch, persist) — the gateway already has the `_load_hardcoded_resume` / `_synthesize_audio` / `_transcribe_audio` helper pattern in `interview.py` to copy.

### 3.3 File-size hot spots

| File                                                             | LOC |
| ---------------------------------------------------------------- | --- |
| `gateway/app/routes/interview.py`                              | 834 |
| `gateway/app/routes/job.py`                                    | 572 |
| `services/question-generation/pipelines/answer_evaluator.py`   | 458 |
| `services/question-generation/pipelines/question_generator.py` | 425 |
| `gateway/app/routes/auth.py`                                   | 226 |

`interview.py` and `job.py` should be split into sub-routers (e.g. `interview/orchestration.py`, `interview/scheduling.py`, `job/applications.py`).

### 3.4 Other observations

- **`E402` in `services/question-generation/pipelines/llm_loader.py:109`** — a `from pathlib import Path` mid-file. Move to top.
- **Tab/space mixing (W191):** 10 tab-indented lines, mostly in CORS middleware blocks (`gateway/app/main.py`, `services/file-service/app/main.py`, `services/transcribe-audio/app/main.py`). Repo otherwise uses spaces.
- **No tests, no `pyproject.toml`, no `pytest`/`mypy` configuration** anywhere in the Python tree. Each service has only `requirements.txt`. Adding a top-level `pyproject.toml` with `[tool.ruff]`, `[tool.mypy]`, and a unified test command is the highest-leverage tooling change.

---

## 4. Security (Bandit)

**Run summary:** 2 Medium, 12 Low, 0 High across 4,141 LOC.

### 4.1 Medium-severity findings

| ID   | Issue                        | File                                                    | Line | Notes                                                                                                                                                                                           |
| ---- | ---------------------------- | ------------------------------------------------------- | ---- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| B108 | Hardcoded `/tmp` directory | `services/text-to-speech/main.py`                     | 16   | `AUDIO_OUTPUT_DIR` defaults to `/tmp/tts_audio`. Acceptable in container, but on a shared host this is predictable & symlink-attackable. Use `tempfile.mkdtemp()` or require the env var. |
| B108 | Hardcoded `/tmp` directory | `services/transcribe-audio/app/routers/transcribe.py` | 12   | Same pattern, same fix.                                                                                                                                                                         |

### 4.2 Low-severity findings (selected)

| ID   | Issue                           | File                                                                               | Notes                                                                                                                |
| ---- | ------------------------------- | ---------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| B110 | `try / except / pass`         | `gateway/app/routes/auth.py:131`                                                 | Silently swallows JWT-decoding errors during login fallback.**Add logging** at minimum.                        |
| B110 | `try / except / pass`         | `services/question-generation/pipelines/answer_evaluator.py:341`                 | OK in JSON-extract heuristic, but log at DEBUG.                                                                      |
| B311 | `random` for non-crypto (×6) | `services/question-generation/pipelines/{flow_controller,question_generator}.py` | False positive — used for question variation, not security. Mark with `# nosec B311` or `secrets` not required. |
| B105 | "Possible hardcoded password"   | `services/question-generation/pipelines/answer_evaluator.py:33,173,217,278`      | False positives —`"pass": False` is a dict key referring to the candidate's pass/fail state. No fix needed.       |

### 4.3 Findings outside Bandit's reach

These were spotted during review and matter more than anything Bandit flagged:

1. **Soft-verify JWT in production code.** `gateway/app/core/security.py:28` calls `jwt.get_unverified_claims(token)` and a comment marks this as "40% Submission". This means **anyone holding a sub claim for an existing user can authenticate** — there is no signature check. Must be replaced with JWKS validation against the Cognito user pool before any external deploy.
2. **Committed secrets.**
   - `gateway/.env` is in the repo with `COGNITO_CLIENT_SECRET` and `DATABASE_URL` (admin/admin123).
   - `infra/docker/docker-compose.yml:137` hardcodes a `GROQ_API_KEY` value.
   - All of these must be rotated; add `*.env` (already covered by root `.gitignore`, but the `gateway/.env` file is checked in despite this — likely tracked before the ignore rule was added).
3. **Default DB credentials baked into code.** `gateway/app/core/db.py:11` and `database/init_db.py:9-13` fall back to `admin/admin123`. Fine for compose; remove the fallback for production builds (fail fast on missing env).
4. **Bare `except Exception` patterns** (≈30 occurrences) silently catch and re-raise as 500 in routes. Combined with `B904` violations, the original error is lost. Pair the `from e` fix with structured logging.
5. **CORS allow-list** uses `["*"]` whenever `FRONTEND_ORIGINS` is unset (`gateway/app/main.py:15`, several services). With `allow_credentials=True`, FastAPI/Starlette will refuse the wildcard at runtime, but it should still be replaced with a hard fail on missing config.

---

## 5. Recommended fixes (prioritized)

### P0 — security / correctness (do before any external deploy)

1. Replace `get_unverified_claims` with full JWKS verification in `gateway/app/core/security.py`.
2. Rotate the Cognito client secret, GROQ key, and DB password — they are in git history. Stop committing `.env` files.
3. Fix the `try/except/pass` in `gateway/app/routes/auth.py:131` to log + decide deliberately.
4. Fix `src/lib/api.ts` `HeadersInit` type error (currently a real `tsc` failure).

### P1 — bug-prone code

5. Remove the dead `llm = LLMLoader(...)` assignment in `services/question-generation/app/main.py:39` (model is being loaded and discarded).
6. Add `from e` chaining on every `raise HTTPException` inside `except` (29 sites).
7. Add the missing `fetchJobs` dep in `src/app/recruiter/job/page.tsx:128` (or wrap in `useCallback`).
8. Refactor `upload_and_parse_resume` (CC=20), `evaluate_and_generate` (CC=16), `parse_resume_by_id` (CC=15) into smaller helpers.

### P2 — hygiene

9. Add `pyproject.toml` at repo root with Ruff config (ignore FastAPI immutable calls), Black/Ruff-format, and a `pytest` placeholder.
10. Run `ruff check --fix` (183 auto-fixable) + `ruff format` once, in a single dedicated commit.
11. Fix the 5 `react/no-unescaped-entities` errors (autofix: `'` → `&apos;`).
12. Split `gateway/app/routes/interview.py` (834 LOC) into a sub-router package.
13. Establish a frontend test setup (Vitest or Jest) and a backend test setup (`pytest`) — currently zero tests exist.

---

## 6. How to reproduce

```sh
# Frontend
cd frontend
npm run lint
npx tsc --noEmit

# Backend (from repo root)
pip install ruff bandit
ruff check gateway/app services/file-service/app services/resume-parser/app \
           services/question-generation/app services/question-generation/pipelines \
           services/transcribe-audio/app services/text-to-speech/main.py \
           services/report-generation/app --select E,F,W,B,C,I --statistics
bandit -r gateway/app services/file-service/app services/resume-parser/app \
          services/question-generation/app services/question-generation/pipelines \
          services/transcribe-audio/app services/text-to-speech/main.py \
          services/report-generation/app -l
```
