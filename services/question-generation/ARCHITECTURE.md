# Question Generation Service: Architecture and Interview Guide

## Purpose and scope

Think of this service as a "next question machine". The gateway (the boss that
runs the whole interview) asks it: "given this resume and what the candidate
said so far, what should I ask next?" The service answers with exactly one
question plus some metadata (category, difficulty, scores).

Simple rules to remember:

- One request in, one question out. The service does NOT run the full
  interview loop — the gateway calls it again for every turn.
- It remembers NOTHING between requests. All history comes inside each
  request. The gateway's database is the real memory.

This document explains how it works, the design choices, the limits, and how
to talk about it in an interview.

## 1. Architecture at a glance

```text
                        +-------------------------------+
                        |        API GATEWAY            |
                        |  (owns interview + history)   |
                        +---------------+---------------+
                                        |  POST /next-question
                                        v
                        +---------------+---------------+
                        |   QUESTION GENERATION SERVICE |
                        |                               |
                        |  FastAPI routes               |
                        |       |                       |
                        |  Orchestrator (thin wrapper)  |
                        |       |                       |
                        |  LangGraph (the traffic cop:  |
                        |   picks which step runs)      |
                        |    |        |         |        |
                        |  Pool    Evaluate   Intro /   |
                        |  picker   answer    Opener    |
                        |    +        +---------+       |
                        |    |     Follow-up   New      |
                        |    |     (retry x1)  topic    |
                        |    |        |         |        |
                        |    v        v         v        |
                        |  { question + metadata }      |
                        +---+-----------------+---------+
                            |                 |
              +-------------+      +----------+----------+
              | CSV question       | Gemini (primary)    |
              | bank (local file)  | OpenRouter (backup) |
              +--------------------+----------+----------+
                                              |
                                   Embeddings (only for
                                   backup scoring)
```

The same `app.main:app` starts in Docker, Procfile, and Nixpacks. There is
also a terminal practice tool in `app/cli.py` (uses the same building
blocks, but you type answers yourself).

### Main parts (each does one job)

| Part | Job in plain words |
|---|---|
| FastAPI app (`app/main.py`) | Starts everything once: settings, AI models, question bank, the graph. Stores them on `app.state` so every request can use them. |
| API router (`app/api/routes.py`) | Three endpoints: `/next-question`, `/draft-email`, `/health`. Thin: it just converts the request and calls the graph. |
| Request schemas (`app/schemas/requests.py`) | Checks the shape of incoming data (resume, history, pool, email fields). |
| Answer schemas (`app/schemas/llm.py`) | Checks the shape of AI answers (question, score, email). Never trust raw AI text until it passes these. |
| Settings (`app/config.py`) | Reads environment variables in ONE place. Nothing else touches `os.getenv`. |
| Chat models (`app/llm/models.py`) | Builds the AI models: Gemini first, OpenRouter as backup. One try each, 60-second limit. |
| Chains (`app/llm/chains.py`) | The recipe `prompt -> model -> parser`, plus automatic fallback to the backup model, plus the scoring branch logic. |
| Prompts (`app/prompts/templates.py`) | All question/scoring/email prompt texts live here. |
| Pure helpers (`app/services/dataset.py`, `evaluation.py`, `text.py`) | Math and text work with no memory between requests: picking questions, scoring, cleaning text. Easy to test. |
| Graph (`app/graph/`) | Decides which step runs for this request (intro? opener? score the answer? follow-up?). |
| Orchestrator (`app/pipelines/orchestrator.py`) | Tiny wrapper: puts the request into the graph, returns question + metadata. |
| Gateway (another service) | Keeps the interview records, picks which category is next, saves each question. |

## 2. How one request flows

### 2.1 The recruiter question pool (free questions, no AI needed)

Sometimes a recruiter uploads their own questions. Those always win — why pay
for AI when a human already wrote the question?

```text
  Request arrives with a pool of recruiter questions
                        |
                        v
        +---> Any question NOT used yet? --- NO ---> normal AI flow
        |                       |
       YES                      v
        |            Prefer one matching the requested
        |            category (ignore big/small letters).
        |            If none matches, take the first
        |            unused one anyway (on purpose).
        v                       |
  Return it with                |
  source = "recruiter_pool" <----+
```

Two details:

- If the candidate already answered something, the service still scores the
  last answer (so the metadata has scores). Scoring can never break this:
  on any surprise error it stores a neutral score and still returns the
  pool question.
- With no history at all, this path makes ZERO AI calls.

### 2.2 The graph: a traffic cop with 4 exits

```text
                    POST /next-question
                             |
                             v
                    +------------------+
                    |   route_entry    |  (first decision)
                    +--+---+---+---+---+
                       |   |   |   |
        history?       |   |   |   |  no history + pool left?
         YES           |   |   |   |  YES
          |            |   |   |   |
          v            v   |   |   v
   +-------------+     |   |   |  +------------------+
   | EVALUATE    |     |   |   |  | PICK POOL        |
   | the answer  |     |   |   |  | QUESTION (no AI) |
   +------+------+     |   |   |  +---------+--------+
          |            |   |   |            |
          v            |   |   |            |
   +-------------+     |   |   |   no history,  no history,
   | route_after |     |   |   |   NO category  + category
   | _eval       |     |   |   |      |            |
   +--+---+---+--+     |   |   |      v            v
      |   |   |        |   |   |  +--------+  +----------+
      |   |   |        |   |   |  | INTRO  |  | OPENER   |
  pool|   |   |        |   |   |  | (hello +|  | (easy Q  |
  left|   |   |        |   |   |  | name,   |  | from the |
      |   |   |        |   |   |  | no AI)  |  | bank)    |
      v   v   v        v   v   v  +---+----+  +-----+----+
     POOL FU  NEW      |   |   |      |             |
          |   |        |   |   |      +------+------+
          v   v        v   v   v             |
   +----------------+  (pool/intro/opener join here too)
   | follow-up node |
   |  (asks the AI  |
   |   for 1 Q)     |
   +--------+-------+
            |
            v
   +----------------+
   | validate it:   |
   | good? -> DONE  |
   | bad + tried    |
   |  < 2 times?    |
   |  -> try AGAIN  |
   |  (with reason) |
   | bad + out of   |
   | tries? -> use  |
   | a TEMPLATE Q   |
   +----------------+
            |
            v
   { question + metadata }  --> back to gateway
```

Legend: FU = follow-up, NEW = new topic. Rule of thumb: the graph only
branches where a real decision exists (entry, after scoring, follow-up
check). Everything else is just a chain (recipe) running inside a step.

Every AI step uses the same recipe:

```text
  Prompt template
        |
        v
  Gemini + "answer in this exact shape"   (primary)
        |
        +--- if it crashes --> OpenRouter prompt + parser (backup)
        |
        v
  Clean-up step (fix text, check shape)
        |
        v
  Save into the request's state
```

The gateway sends history from ONE category only (not the whole interview).
That is on purpose: the service gets a small, focused window, not a huge
transcript. Scores of `deep_dive` / `same_topic` mean "ask a follow-up",
`new_topic` means "pick a fresh question".

### 2.3 Picking a new question, and plan B for failures

New topic (no follow-up needed):

1. Look in `data/software_questions.csv` for the requested category +
   difficulty, skipping questions the candidate already saw (matched from
   THIS request's history, not from server memory).
2. If almost nothing is left, loosen the rules step by step (allow seen
   ones, then allow any difficulty, then whole file).
3. No resume? Return the question as-is (sometimes with a friendly prefix
   like "I'd like to know: ").
4. Resume present? Ask the AI to rewrite the question around the candidate's
   skills/projects. If the AI returns garbage (empty or way too long), use
   the original question.

Follow-up: ask the AI for ONE deeper question using the last Q, the last A,
the score, and the resume. Check it locally (ends with `?`, 10+ characters,
max 30 words, shares 1–10 meaningful words with the answer). Bad? Try once
more, telling the AI why the last try failed. Still bad, or AI is down? Use
a ready-made template like "What trade-offs did you weigh the last time you
used {topic}...?" — so the candidate ALWAYS gets a question.

One request = one question. The gateway repeats this call for every turn.

### 2.4 Writing candidate emails (separate feature)

`POST /draft-email` does not touch the question graph. It:

1. Checks the input (scenario, name, job title required).
2. Picks instructions for the scenario (`shortlisted`, `interview_scheduled`,
   `stage_advance`, `rejection`, `offer`, `custom`).
3. Fills in name, role, company, date, scores.
4. Asks the AI for `{subject, body}` and rejects empty results.

It never saves anything — just returns the draft.

## 3. Data: what goes where

```text
  Candidate answers, recruiter uploads resume + settings
        |
        v
  GATEWAY (database: interviews, Q/A per category, used pool questions)
        |  POST /next-question  (resume + same-category history)
        v
  THIS SERVICE (no database!)
        |
        +-- pool left? --> return recruiter question (+ score last answer)
        |
        +-- else --> graph: intro / opener / score -> follow-up / new topic
        |                |           |
        |           CSV file    Gemini / OpenRouter (AI calls)
        |                           |
        |                      embeddings (only for backup scoring)
        v
  { question + metadata } --> gateway saves it, interview continues
```

| Data | Where it is used here | Who keeps it afterwards |
|---|---|---|
| Resume | Hello-name + short skills/projects text for prompts | Gateway (we store nothing) |
| Past Q/A (same category) | Scoring the last answer, follow-up context, skipping seen questions | Gateway |
| Difficulty / category | Filtering the question bank, prompt hints | Gateway |
| Recruiter pool | Pick first unused (prefer matching topic) | Gateway |
| Question bank (CSV) | Starting questions + reference answers | A file in this repo |
| Prompts / AI replies | Making questions, scores, emails | Nobody (used once, thrown away) |
| Embeddings | Backup scoring when AI is down | Used once in memory |
| Final question + metadata | The answer we return | Gateway saves it |

`QuestionGraphState` lives for ONE graph run only. It is scratch paper, not
memory.

## 4. Scoring answers (and picking what to do next)

Scoring gives TWO things:

1. **Evaluation** (for humans to read): pass/fail, score 0–1, confidence,
   one-line feedback.
2. **Flow decision** (for the graph): `new_topic` (move on), `same_topic`
   (answer was weak, probe again), `deep_dive` (answer was strong, go
   deeper).

Cheap checks first — NO AI call for obvious cases:

```text
  Answer arrives
       |
       +-- shorter than 3 chars? -----> score 0.1, same_topic
       |
       +-- "I don't know" pattern? ----> score 0.0, new_topic (just move on)
       |
       +-- fewer than 5 words? -------> score 0.2, same_topic
       |
       +-- else --> ONE AI call: score + feedback + decision together
                         |
                         +-- AI down? --> backup math (below)
```

Backup math: with a reference answer,
`0.5 x meaning-similarity + 0.3 x shared-keywords + 0.2 x answer-length`;
without one, just answer-length capped at 1.0. Score >= 0.55 = pass.
Note: the graph follows the DECISION, not just pass/fail — a great answer
can still earn a `deep_dive`.

## 5. AI providers (the phone book)

### How a call works

```text
  prompt template  -->  GEMINI (primary)  --crash-->  OPENROUTER (backup)
        | даёт structured shape        | plain text + parser
        v                              v
              clean / validate --> return
```

- Gemini first (if `GEMINI_API_KEY` exists), OpenRouter second. Each gets
  exactly ONE try (`max_retries=0`, 60s limit). That is fallback, not
  endless retrying.
- Gemini is asked for the answer in an exact shape (`with_structured_output`).
  Cheap OpenRouter models often can't do that trick, so the backup uses
  plain text + `PydanticOutputParser` (which also handles ```json fences).
- Bad shape = error, handled per feature: question → template, scoring →
  backup math, email → HTTP 500.
- For Gemini 2.5, "thinking" is capped so it can't eat the tiny 150-token
  budget and return an empty question.
- Every chain is tagged for tracing. Tracing turns on via env vars only —
  resumes and answers NEVER go into tags/metadata.

Settings (all in `.env.example`):

| Variable | Plain meaning |
|---|---|
| `GEMINI_API_KEY` | Turns on Gemini (chat + embeddings). |
| `GEMINI_CHAT_MODEL` | Which Gemini model (default `gemini-2.5-flash`). |
| `OPENROUTER_API_KEY` | Turns on the backup. Alone, it can run the whole service. |
| `LLM_FALLBACK_MODEL` | Backup model when Gemini exists (default `meta-llama/llama-3.1-8b-instruct:free`). |
| `LLM_PRIMARY_MODEL` | Model when ONLY OpenRouter exists. |
| `APP_URL` | Sent as referer header to OpenRouter. |
| `LLM_TIMEOUT_SECONDS` | One-try time limit (default `60`). |
| `EMBEDDING_MODEL` / `EMBEDDING_DIMS` | Embedding model + size (defaults `gemini-embedding-001` / `768`). |
| `MAX_FOLLOWUPS_PER_TOPIC` | Max follow-ups in a row (default `2`), only when history marks follow-ups. |

No key at all = crash at startup with a clear error. Secrets stay in env
vars, never in code/docs.

### Embeddings (the backup scorer's helper)

One client, created LAZILY (only when first needed). No key = no client, and
the service still starts (important for OpenRouter-only setups). Scoring
uses async calls, so the server never freezes waiting. If embeddings exist
but a call fails, similarity counts as neutral 0.5. If no client exists at
all, the meaning-term is dropped and the other weights are scaled up.

## 6. Why it is built this way

| Choice | Why (one line each) |
|---|---|
| Folders by job (`api`, `schemas`, `services`, `graph`, ...) | Change HTTP code without touching prompts, and vice versa. |
| All startup in `main.py` | One place builds everything; requests just use it. |
| Shared objects on `app.state` | No global variables leaking between tests or requests. |
| `Field(default_factory=list)` for history | Every request gets its own fresh list. |
| LangGraph for one turn | Branching (intro/opener/score/follow-up) is written down and testable; NOT used as interview memory. |
| No checkpoint DB, no vector DB | Nothing to remember + tiny local CSV = no extra servers needed. |
| One model-building module | Timeout, fallback rule, and model names in one spot. |
| Pydantic output shapes | AI text is checked BEFORE we use it (shape only, not truth). |
| Pool questions first | Recruiter's own words win; saves time and money. |
| CSV seeds + AI rewrite | Bounded topics from the file, personal touch from AI, safe fallback to the original. |
| Free checks before AI calls | "idk" and tiny answers cost $0 to handle. |
| One AI call for score + decision | Half the waiting, half the cost of two calls. |
| Backup scoring math | Interview continues even if both AI providers are down (rough score, not a hiring verdict). |
| Gateway keeps all records | This service stays replaceable; run 1 or 100 copies, no shared memory. |
| 2 Gunicorn workers | Two processes handle requests; each loads its own copy of everything. |

## 7. Honest limits (read before production)

1. **No cross-interview memory — by design.** Skipped-question IDs come from
   THIS request's history only. Nobody else's interview can affect yours.
2. **Topic-skipping needs gateway help.** History items CAN carry `category` /
   `is_followup` / `reference_answer`, but the gateway today sends only `Q`
   and `A`, so those extras stay unused until the gateway sends them.
3. **Backup scores are rough.** Fine for keeping the interview alive, NOT for
   real hiring decisions without calibration + human review.
4. **Failed embedding = neutral 0.5.** "No client at all" is handled better
   (weights rescaled), but a mid-call failure still looks like average
   similarity. Worth making visible later.
5. **Pool scoring is best-effort.** If scoring blows up, the question is still
   returned; treat missing scores as "unknown", not "good".
6. **Shape-check is not truth-check.** A perfect-shaped question can still be
   boring or repetitive. Quality checks are a future add-on.
7. **Backup = slower worst case.** Gemini timeout + OpenRouter try can stack.
   Keep the gateway's own timeout in mind.
8. **Embeddings have no guard rails yet.** A semaphore/circuit-breaker could
   help if the provider keeps failing.
9. **`/health` is shallow.** It says "I'm alive", not "AI works". Monitor
   providers separately.
10. **Resumes go to outside providers.** Even trimmed. Needs approved
    data/retention settings + access control.
11. **No auth in these routes.** The gateway is the public face; lock this
    service to private network only.
12. **Each worker loads everything.** More workers = more memory + startup
    cost; scale with provider limits in mind.

## 8. Interview Q&A (short + technical)

### Structure

**Q1. Why separate `api`, `schemas`, `services`, `graph`, `prompts`?**
A. Separation of concerns: transport, contracts, pure logic, routing,
prompts. I can change prompts without touching HTTP code, and test logic
with stubbed chains.

**Q2. Why build everything in `main.py` lifespan, not per request?**
A. Models, chains, dataset, and the compiled graph are expensive and
stateless — build once, share via `app.state`, keep requests cheap.

**Q3. Why `app.state` instead of globals?**
A. Globals leak between app instances in tests and hide ownership. `app.state`
is scoped to the app's lifespan.

**Q4. Why LangGraph for a single turn?**
A. The turn has real branches (intro / opener / evaluate -> follow-up or new
topic, plus a retry loop). A graph makes states and transitions explicit and
testable. No checkpointer: the gateway owns durable state.

**Q5. Why doesn't this service run the whole interview?**
A. Single responsibility + single source of truth. The gateway owns records,
scheduling, and category order. Two loops would mean two truths.

**Q6. Why no vector DB or checkpointing?**
A. No retrieval need: context is small (same-category history) and the bank
is a 200-row CSV. Add infra only after a measured need.

### Flow

**Q7. What happens with a recruiter pool?**
A. Deterministic pick inside the graph: first unused question matching the
category, else first unused. Zero LLM calls without history; with history the
last answer is scored first (never raises).

**Q8. How is intro vs opener vs evaluate chosen?**
A. `route_entry`: history -> evaluate; unused pool item -> pool; no category
-> intro; else easy category opener.

**Q9. When is a follow-up asked?**
A. Decision `same_topic`/`deep_dive` -> follow-up (capped by
`MAX_FOLLOWUPS_PER_TOPIC` when history flags follow-ups); else new topic.

**Q10. How is a new question picked?**
A. Filter CSV by category + difficulty minus per-request `exclude_ids`,
relaxing constraints stepwise; prefer topics outside the last 3 covered;
personalize via LLM only when a resume snippet exists.

**Q11. Follow-up fails checks or the LLM is down?**
A. Retry once with the rejection reason, then a topic template. Personalize
failure falls back to the raw seed. Delivery never depends on the LLM.

### Providers & reliability

**Q12. How do you avoid blocking the event loop?**
A. Fully async clients (`ChatGoogleGenerativeAI`, `ChatOpenAI`,
`aembed_documents`). No threads, no sync SDK in the request path.

**Q13. Retry or fallback?**
A. Fallback, bounded: `max_retries=0` per provider, 60s timeout each, Gemini
then OpenRouter via `.with_fallbacks` on finished chains.

**Q14. What does structured output guarantee?**
A. Shape and field constraints only (via `with_structured_output` /
`PydanticOutputParser`) — not correctness, fairness, or factuality.

**Q15. Why an OpenRouter fallback?**
A. Second provider path with zero interface change; also enables
OpenRouter-only deploys via `LLM_PRIMARY_MODEL`. Trade-off: worst-case
latency doubles.

**Q16. LLM down during scoring?**
A. Short-circuits first (empty/idk/brief), else heuristic:
`0.5*similarity + 0.3*keywords + 0.2*length` (or length-only). Rough, not a
hiring signal.

### State & ops

**Q17. Is graph state the interview memory?**
A. No — one `ainvoke`, then gone. Gateway passes history in and persists the
result out.

**Q18. Can one candidate's interview affect another's?**
A. No. `DatasetRepository` is immutable; `exclude_ids` derive from the
current request only. Workers share nothing.

**Q19. Effect of multiple Gunicorn workers?**
A. Each is an independent process with its own lifespan (models, CSV,
graph). More throughput, no shared state.

**Q20. What does `/health` prove?**
A. Liveness only. Providers/keys are NOT checked — monitor those separately.

**Q21. First production improvement?**
A. Make heuristic degradation observable (metrics/logs), then latency
budgets, timeout contract tests, auth/network policy, data-retention review.

**Q22. Testing without paid API keys?**
A. `RunnableLambda` stubs for `Chains`, fake models for `make_chat_models`,
in-memory `DatasetRepository`. 47 tests, zero network.

**Q23. Why is email outside the graph?**
A. Different workflow, different schema — shares only the model builders.
Putting it in the graph would couple unrelated flows.

**Q24. Is a valid email safe to send?**
A. No. Schema = non-empty subject/body; prompt = "don't invent facts".
Still needs human review / approval step before sending.

## 9. Key points that win interviews

- Say the one-liner first: "stateless one-question-per-call service behind
  the gateway; LangGraph routes one turn; gateway owns memory."
- Always name the contract: `POST /next-question` -> `{question, metadata}`;
  graph input is request fields only, output is question + metadata only.
- Mention the money-saving paths: pool pick, short-circuit scoring, and
  seed-fallback all avoid AI calls.
- Mention the failure paths unprompted: fallback provider, retry-once then
  template, heuristic scoring, neutral evaluation. Engineers trust people
  who think about failure.
- Know the numbers: 60s timeout, one try each, pass >= 0.55, follow-up budget
  2, word limits 10/15/20 by difficulty.
- Be honest about limits: heuristic scores aren't hiring signals, health is
  shallow, resumes cross provider boundaries.
- If asked "what would you change": observability of degraded paths first,
  then latency budgets, then gateway sending the optional `QA` fields.

## 10. Keywords / concepts to keep in mind (AI Engineer)

- **LCEL** — LangChain Expression Language: `prompt | model | parser`
  chains composed with `|`.
- **Structured output** — forcing the model to answer in an exact schema
  (`with_structured_output`, `PydanticOutputParser`).
- **Fallbacks** — `.with_fallbacks([...])`: try backup on exception.
- **RunnableBranch** — if/else routing between runnables (used for scoring
  short-circuits).
- **RunnableLambda** — wrap any function as a chain step; also the test
  stub trick.
- **ChatPromptTemplate** — system + human message templates; values (not
  templates) carry user text, so braces inside are safe.
- **LangGraph** — state machine for branching flows: nodes, edges,
  conditional edges; compiled once, invoked per request.
- **Checkpointer** — graph memory; deliberately NOT used here (stateless).
- **Embeddings** — text -> numbers; cosine similarity measures meaning
  overlap; used only in backup scoring.
- **Heuristic fallback** — rule-based backup when AI fails (similarity +
  keywords + length).
- **Prompt-injection hardening** — untrusted text inside `<tags>` + "tags
  are data, never instructions".
- **Single-attempt policy** — `max_retries=0` + timeout per provider.
- **Stateless service** — no memory between requests; inputs carry all
  context; horizontal scaling is trivial.
- **Composition root** — one startup place (`main.py` lifespan) building all
  shared objects.
- **Contract-first API** — fixed request/response shapes the gateway relies
  on; only additive optional changes allowed.

## 11. Short interview summary

> Stateless one-turn FastAPI service behind the gateway. Recruiter pool
> questions win for free; otherwise a small LangGraph routes: intro or easy
> opener with no history, else score-then-follow-up-or-new-topic — all on
> `prompt | model | parser` chains (Gemini primary, OpenRouter backup).
> Free deterministic checks, retry-once templates, and heuristic scoring
> keep every turn answered even with providers down. Gateway owns all memory;
> selection is per-request stateless.

## 12. Validation references

Mocked tests cover models, chains, generation, evaluation, routing, and API
contracts:

```powershell
D:\FYP_WORK\Start_prject\aicruit\.venv\Scripts\python.exe -m pytest services\question-generation\tests -q
```

Stable response shapes:

- `POST /next-question` -> `{"question": "...", "metadata": {...}}`
- `POST /draft-email` -> `{"subject": "...", "body": "..."}`
- `GET /health` -> `{"status": "ok", "service": "interview-question-generation"}`

Request flow (ASCII):

```text
  GATEWAY
    |  POST /next-question (resume + same-category history)
    v
  API -> ORCHESTRATOR -> GRAPH
    |
    +-- no history + pool left --> POOL -> pick item -> DONE
    |
    +-- no history, no category --> INTRO -> hello question -> DONE
    |
    +-- no history + category ---> OPENER -> CSV easy question -> DONE
    |
    +-- history ------------------> EVALUATE last answer (AI or free checks)
         |
         +-- pool left -----------------> POOL -> DONE
         |
         +-- same_topic / deep_dive -----> FOLLOW-UP (AI, retry once,
         |                                 then template) -> DONE
         |
         +-- new_topic -------------------> CSV seed (+ AI rewrite if resume)
                                           -> DONE
    |
    v
  { question + metadata } -> GATEWAY saves it, interview goes on
```
