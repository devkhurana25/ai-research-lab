<div align="center">

# 🔬 AI Research Lab

**An autonomous research pipeline that investigates data the way a scientist would —
profiling, hypothesizing, testing, critiquing itself, and citing its evidence.**

Ask it a question. Give it a dataset. It gives back a report you can actually audit,
not a paragraph it made up.

[![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Backend-green?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-Frontend-black?logo=next.js)](https://nextjs.org/)
[![Docker](https://img.shields.io/badge/Docker-Containerized-2496ED?logo=docker)](https://www.docker.com/)
[![Railway](https://img.shields.io/badge/Railway-Deployed-black?logo=railway)](https://railway.app)
[![Supabase](https://img.shields.io/badge/Supabase-PostgreSQL%20%2B%20pgvector-3FCF8E?logo=supabase)](https://supabase.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-Orchestration-purple?logo=graph)](https://github.com/langchain-ai/langgraph)
[![Scikit-Learn](https://img.shields.io/badge/scikit--learn-ML%20Pipeline-F7931E?logo=scikitlearn)](https://scikit-learn.org/)
[![Vercel](https://img.shields.io/badge/Vercel-Frontend%20Hosting-black?logo=vercel)](https://vercel.com)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

[Live Demo](https://ai-research-lab-indol.vercel.app/) · [API Reference](https://ai-research-lab-production.up.railway.app/docs) · [Deploy Your Own](#deployment)

</div>

---

## What this is

Most "AI analytics" tools either run a canned dashboard or let an LLM freestyle
over your data and hope it doesn't hallucinate a number. This project does
neither. A LangGraph-orchestrated agent pipeline decomposes your question,
runs real statistics (SciPy) and real ML (scikit-learn) against your actual
data, generates competing hypotheses, tries to *disprove* its own conclusions,
and only then writes a report — every claim in that report traces back to a
computation you can inspect.

An optional local LLM (Ollama) layer sits on top for the parts that genuinely
benefit from natural-language reasoning — a chat panel to interrogate a
finished report, "what-if" exploration, competitor-angle brainstorming — kept
separate from the statistical core so the numbers are never something an LLM
invented.

## Key features

**Agentic investigation pipeline**
- Orchestrated with **LangGraph**: explicit states, a bounded revision loop, a
  recursion-limit backstop — this cannot spin forever even if the critic keeps
  objecting
- Specialized agents: Data Scientist, Statistical Analyst, Hypothesis
  Generator, Experiment Runner, ML Experiment (scikit-learn), Critic, Report
  Generator
- The **Critic** actively tries to break the investigation's own conclusions —
  catches unsupported causal language, thin sample sizes, and hypotheses with
  no independent test behind them — and can send the whole thing back for
  revision

**Real statistics and ML, never fabricated**
- Welch's t-test, Pearson correlation, OLS trend analysis (SciPy), with
  assumption checks surfaced, not hidden
- RandomForest regression (scikit-learn) with honest train/test metrics —
  explicitly skips fitting a model rather than faking one when there isn't
  enough data to support it

**Retrieval-augmented research**
- Local document RAG (PDF and text) with a selectable backend:
  `RETRIEVAL_BACKEND=tfidf` (zero dependencies) or `pgvector` (semantic,
  via Postgres) — `auto` picks pgvector when a Postgres `DATABASE_URL` is
  configured, TF-IDF otherwise
- Optional live web search, attempted only when local documents don't
  already answer the question — never fired unnecessarily

**Conversational report exploration (Ollama)**
- A local **Ollama** (`llama3`) integration powers a report-discussion panel:
  once an investigation finishes, ask follow-up questions and it answers
  using the actual report, hypotheses, and critique as context
- Runs entirely on your own machine — no API key, no per-token cost, no data
  leaving your network

**Full-stack, not a notebook**
- **FastAPI** backend with JWT authentication, per-user data isolation, live
  progress via **Server-Sent Events**, and PDF export
- **Next.js** frontend with a deliberate visual identity (not default
  component-library styling): a live investigation dashboard, dataset
  explorer, evidence graph, investigation/task graph, and an observability
  view
- **PostgreSQL + pgvector** for persistence and vector search (SQLite
  fallback for zero-setup local use)

**Built to be trusted, not just to work**
- Every capability in this README has a test behind it — see
  [Testing](#testing) — and the project's own commit history includes real
  bugs that were found and fixed by testing, not assumed away (see
  [Known issues found & fixed](#known-issues-found--fixed))

---

## Architecture

```
┌──────────────────────┐      ┌──────────────────────┐      ┌────────────────────────────┐
│   Next.js Frontend    │ ───▶ │   FastAPI Backend     │ ───▶ │  LangGraph Orchestrator     │
│   (Vercel)            │◀─SSE─│   (Railway)           │      │                             │
│                       │      │                       │      │  Data Scientist             │
│  /            landing │      │  /auth/*   JWT login  │      │  Researcher (local + web)   │
│  /login       auth UI │      │  /investigations      │      │  Hypothesis Generator       │
│  /lab      live dash  │      │  /investigations/     │      │  Experiment Runner          │
│  /explorer  dataset   │      │      stream (SSE)     │      │  ML Experiment (sklearn)    │
│  /admin   observab.   │      │  /datasets/profile    │      │  Critic ──revise?──┐        │
│                       │      │  /admin/stats         │      │       │            │        │
└──────────────────────┘      │  /ollama-query        │      │       ▼            │        │
                                │  /chatbot             │      │  Report Generator │        │
                                │  /generate-report     │      │       │            │        │
                                └──────────┬────────────┘      └───────┼────────────┘        │
                                           │                            │           loop back ┘
                                           ▼                            ▼
                                ┌──────────────────────┐      ┌─────────────────────┐
                                │  Supabase (Postgres   │      │  Ollama (local)      │
                                │  + pgvector)          │      │  llama3              │
                                │  scoped by user_id    │      │  report Q&A only     │
                                └──────────────────────┘      └─────────────────────┘
```

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | Next.js, TypeScript, Tailwind CSS, self-hosted fonts (`@fontsource`) |
| Backend | FastAPI, Python 3.12, Pydantic |
| Orchestration | LangGraph |
| Data science / ML | pandas, NumPy, SciPy, scikit-learn |
| Retrieval | TF-IDF (scikit-learn) or pgvector, selectable |
| Database | PostgreSQL + pgvector (Supabase), SQLite fallback |
| Auth | JWT (python-jose) + bcrypt |
| Local LLM | Ollama (`llama3`) |
| PDF generation | fpdf2 (+ chart rendering) |
| Containerization | Docker, Docker Compose |
| Hosting | Vercel (frontend), Railway (backend), Supabase (database) |
| CI | GitHub Actions |
| API testing | Postman collection (`/postman`) |

---

## Getting started

### Prerequisites
- Python 3.11+
- Node.js 18+
- [Ollama](https://ollama.com) (optional — only needed for the chat/Q&A panel and AI-assisted report narration)
- Docker (optional — only needed for the containerized path)

### 1. Backend

```bash
git clone <your-repo-url>
cd ai-research-lab
pip install -r requirements.txt
cp .env.example .env          # see Environment Variables below
pytest tests/ -v               # confirm the install is healthy
uvicorn api:app --reload       # http://localhost:8001
```

### 2. Frontend

```bash
cd web
npm install
cp .env.local.example .env.local   # set NEXT_PUBLIC_API_URL
npm run dev                         # http://localhost:3000
```

### 3. (Optional) Local LLM for report Q&A

```bash
ollama pull llama3
ollama serve
```
The backend talks to `http://localhost:11434` by default — override with
`OLLAMA_BASE_URL`. Nothing else in the app depends on this; investigations
run and produce full reports with or without Ollama running. If it's
unavailable when a PDF is generated, the PDF still includes the full
deterministic analysis, with a note that the AI narrative section couldn't
be generated.

### 4. (Optional) Docker Compose — everything together

```bash
docker compose up --build
```
Spins up the API, the frontend, and Postgres+pgvector together. On macOS/
Windows, a host-installed Ollama is reachable from inside the containers at
`host.docker.internal:11434` (already the Compose default — override via
`OLLAMA_BASE_URL` if yours runs elsewhere).

---

## Environment variables

| Variable | Required | Purpose |
|---|---|---|
| `DATABASE_URL` | No | Postgres connection string (Supabase or self-hosted). Omit to use SQLite locally. |
| `JWT_SECRET` | Recommended | Signs auth tokens. Set a real random value outside local dev. |
| `API_KEY` | No | Shared key required in `X-API-Key` for the sandboxed `python_code` investigation option. Leave unset to disable that feature. |
| `RETRIEVAL_BACKEND` | No | `auto` (default) \| `tfidf` \| `pgvector`. `auto` uses pgvector when `DATABASE_URL` is set. |
| `OLLAMA_BASE_URL` | No | Defaults to `http://localhost:11434`. |
| `OLLAMA_REPORTS` | No | Set `true` to have Ollama also synthesize the investigation's narrative markdown. |
| `GROQ_API_KEY` | No | Free-tier alternative LLM provider (no credit card) for hypothesis-stage reasoning, if you don't want to run Ollama locally. |
| `ANTHROPIC_API_KEY` | No | Paid alternative to the above — only set this if you specifically want Claude and accept the per-token cost. |
| `NEXT_PUBLIC_API_URL` | Yes (frontend) | Where the frontend finds the backend. |

Nothing here is required for the core statistical pipeline to run and
produce a full report — every LLM-related variable is additive.

---

## API reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/auth/register` | Create an account (email + password) |
| `POST` | `/auth/login` | Get a JWT session token |
| `GET` | `/auth/me` | Current user info |
| `POST` | `/investigations` | Run a full investigation synchronously |
| `GET` | `/investigations/stream` | Same, streamed live via Server-Sent Events |
| `GET` | `/investigations` | List your own past investigations |
| `GET` | `/investigations/{id}/report` | Fetch a completed report (JSON) |
| `GET` | `/investigations/{id}/report.pdf` | Export as PDF |
| `POST` | `/generate-report` | Generate a report directly from `dataset_path`, `dataset_json`, or raw `csv_data` |
| `GET` | `/datasets/profile` | Dataset explorer: schema, missing values, outliers, correlations |
| `POST` | `/ollama-query` | One-off question to the local LLM |
| `POST` | `/chatbot` | Multi-turn chat about a finished report (`conversation_id` to continue a thread) |
| `GET` | `/admin/stats` | Aggregate observability: runtimes, per-agent timing, revision-cycle usage |
| `GET` | `/health` | Liveness check |

A ready-to-import **Postman collection** covering all of the above lives in
[`/postman`](./postman) — import it and set `base_url` and `token` as
collection variables to get started without writing any requests by hand.

---

## Testing

```bash
pytest tests/ -v                 # unit + API integration tests
python evaluations/benchmark.py  # end-to-end pipeline benchmarks
```

The test suite is what backs every checkmark in this README, not the other
way around — if a feature is described above, there's a test exercising it
in `tests/test_pipeline.py` or `tests/test_api.py`. Backend integration
tests run against SQLite by default; point `DATABASE_URL` at a live
Postgres/pgvector instance to also exercise that path.

## Known issues found & fixed

Kept here deliberately — this is a more honest signal of project quality
than a feature list alone:

1. **Cross-user data leak.** The orchestrator originally persisted an
   investigation before the API layer attached the requesting user's ID,
   and the database upsert never updated `user_id` on conflict — every
   investigation was silently saved as unowned, so any authenticated user
   could read any other user's report by ID. Fixed by moving persistence
   entirely into the API layer; regression-tested.
2. **PDF renderer crash on realistic reports.** The PDF library's cursor
   drifts right across cells instead of resetting to the left margin,
   eventually leaving zero width on a later line. Only surfaced on a real
   multi-section report, not a short smoke test. Fixed by explicitly
   resetting the cursor before every write.
3. **Admin stats silently dropping owned investigations.** The
   per-user ownership check used for regular API reads was being reused,
   unmodified, for the admin aggregation — which meant it also blocked the
   admin view from reading any investigation that belonged to a real user.
   Fixed with a dedicated internal accessor that intentionally bypasses
   per-user scoping for the admin view only.

## Honest gaps

Things this project does **not** claim to solve, so you don't have to find
out the hard way:

- `/admin/stats` has no role/permission gate yet — anyone with a token can
  view it. Fine for a solo or portfolio deployment; add role checks before
  using this with multiple untrusted users.
- No rate limiting or upload size/type hardening.
- No password reset or email verification flow — registration and login
  only.
- Live web search degrades gracefully to "no results" if the search
  provider is unreachable, by design — it will never fabricate a source.
- LLM-token/cost tracking isn't in `/admin/stats` — the statistical core
  doesn't use an LLM at all, so there's nothing to meter there by default.

## Deployment

| Piece | Provider | Notes |
|---|---|---|
| Frontend | **Vercel** | Set **Root Directory** to `web` (this is a monorepo). Set `NEXT_PUBLIC_API_URL` to your backend's URL. |
| Backend | **Railway** | Deploy from the repo root; set the start command to `uvicorn api:app --host 0.0.0.0 --port $PORT`. Add all backend env vars from the table above. |
| Database | **Supabase** | Create a project, enable the `vector` extension in the SQL editor, and use the connection string as `DATABASE_URL`. |
| CI | **GitHub Actions** | Runs the full test suite and both builds on every push; wire your Railway/Vercel deploy hooks as repo secrets to gate deploys on tests passing rather than deploying independently of them. |

A `docker-compose.yml` is included for a self-hosted, single-command
deployment of the API, frontend, and a local Postgres+pgvector instance
together.

---

## Project structure

```
ai-research-lab/
├── agents/              # data_scientist, researcher, hypothesis, experiment,
│                         ml_experiment, critic, report
├── core/                # orchestrator (LangGraph), state, auth, observability
├── tools/                # dataset_tools, statistics, retrieval, web_search,
│                         python_executor, pdf_export
├── database/             # SQLite + Postgres/pgvector backends, auto-selected
├── evaluations/          # end-to-end benchmark cases
├── tests/                # pytest suite backing every claim in this README
├── postman/              # Postman collection for the API
├── web/                  # Next.js frontend (Vercel deploy root)
├── sample_data/          # example CSV + PDF for a first test run
├── docker-compose.yml
├── render.yaml            # alternate deploy target (Render)
├── .env.example
└── requirements.txt
```

---

## License

Apache 2.0 — see [LICENSE](./LICENSE).
