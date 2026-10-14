# Runtime Validation Report

**Generated**: 2026-10-14  
**Target**: `services/question-generation`  
**Latest interview input**: `../resume-parser/parsed/Resume.json` (`result` payload)

## Summary

| Step | Status | Exit Code | Details |
|---|---|---:|---|
| Startup | PASS | 0 | Uvicorn started the actual FastAPI app on loopback; `GET /health` returned 200; lifespan loaded the service dataset and constructed the pipeline. |
| Multi-turn interview API | PASS | 0 | Health and three successive `/next-question` turns returned 200 using the parsed dummy resume and deterministic local LLM/evaluation doubles. |
| Regression tests | PASS | 0 | 13 Question Generation tests passed; 0 failed, including a reusable three-turn HTTP API test. |
| Python compilation | PASS | 0 | `compileall` completed successfully. |

**Overall**: PASS for the Question Generation service's multi-turn API flow with mocked provider behavior. The gateway's persisted audio interview was not run.

## Environment

- **Docker**: UNAVAILABLE — Docker CLI check reported that the daemon was not responding. No database or other containerized infrastructure is required by the Question Generation request path tested here.
- **Node.js**: AVAILABLE — `v22.17.1`.
- **Playwright**: NOT REQUIRED — this is an API-only service with no browser-rendered interface; HTTP validation used Uvicorn and `httpx`.
- **External provider access**: Intentionally mocked. Resume contents were not sent to Gemini, OpenRouter, or any other external provider.
- **Latest API test mode**: FastAPI `TestClient` exercised the application lifespan and real HTTP route handlers in-process; no network listener was required.

## Runtime Flow Evidence

The service was started with Uvicorn and exercised over HTTP on a temporary
loopback port. The application lifespan loaded the 200-row question bank.
The resume-parser file is a metadata wrapper; the candidate resume object was
read from its `result` field. The report does not reproduce any resume content.

| Flow | Result |
|---|---|
| Health/readiness route | HTTP 200 |
| Resume-based introduction | HTTP 200; introduction route and resume payload accepted |
| Category opener | HTTP 200; category dataset path returned an easy opener |
| Answer evaluation → follow-up | HTTP 200; mocked `same_topic` decision routed to follow-up |
| Answer evaluation → new topic | HTTP 200; mocked `new_topic` decision routed to dataset-based contextual generation |
| Recruiter question pool | HTTP 200; eligible pool item returned without generation |

Structured mock LLM calls: **4**. External provider calls: **0**. The Uvicorn
server was shut down after the test.

## Multi-turn Interview Run

The latest run used `services/resume-parser/parsed/Resume.json`, passing its
`result` payload to the Question Generation API. Resume values are not
reproduced here. A local LLM double returned structured questions and
deterministic evaluations to exercise both interview branches.

| Request | Result |
|---|---|
| `GET /health` | HTTP 200 |
| First `POST /next-question` | HTTP 200; introduction generated from resume context |
| Second `POST /next-question` with prior Q&A | HTTP 200; `same_topic` evaluation routed to follow-up |
| Third `POST /next-question` with accumulated Q&A | HTTP 200; `new_topic` evaluation routed to a new question |

Evaluations: **2**. External provider calls: **0**.

## Regression Test Evidence

Latest targeted test:

```powershell
D:\FYP_WORK\Start_prject\aicruit\.venv\Scripts\python.exe -m pytest services\question-generation\tests\test_interview_runtime.py -q
```

Result: `1 passed`, exit code `0`.

Latest full suite:

```powershell
D:\FYP_WORK\Start_prject\aicruit\.venv\Scripts\python.exe -m pytest services\question-generation\tests -q
```

Result: `13 passed in 1.71s`, exit code `0`.

Latest compilation:

```powershell
D:\FYP_WORK\Start_prject\aicruit\.venv\Scripts\python.exe -m compileall -q services\question-generation
```

Result: exit code `0`.

Earlier baseline: `12 passed in 1.63s`, before the runtime interview test was added.

## Coverage Limits and Follow-up

- This validates local startup, HTTP routing, graph branches, dataset selection,
  resume payload handling, and structured-output consumer behavior with mocked
  outputs.
- The latest request flow called the Question Generation service directly, not
  the gateway's `/interview/start` or `/interview/evaluateAndGenerate`
  endpoints. The gateway and dependencies were not running: ports 8000,
  8005-8007, and 8010-8012 had no listeners; Postgres port 5432 had no listener;
  Docker's daemon was unavailable.
- Therefore, this run did not verify Cognito/JWT auth, interview database
  persistence, audio transcription, TTS playback, interview completion, or
  report generation.
- It does **not** establish that real Gemini/OpenRouter credentials, provider
  quotas, model behavior, network access, or live embedding calls work.
- Added `tests/test_interview_runtime.py` to preserve the multi-turn API check.
  No Question Generation production code or resume-parser output was changed.
- To test real provider connectivity, first obtain explicit approval to send
  resume-derived prompt context to the configured external provider; otherwise
  keep using provider mocks or a synthetic, non-sensitive resume.
