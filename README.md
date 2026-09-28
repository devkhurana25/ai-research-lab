# AI Research Lab

An autonomous research pipeline: give it a question and a dataset, it
profiles the data, generates hypotheses, tests them statistically and
with ML where the data supports it, critiques its own conclusions, and
produces an evidence-backed report — through a real orchestrated agent
graph, a Postgres+pgvector backend, multi-user auth, live progress
streaming, observability, and a Next.js frontend with a deliberate
visual identity rather than default styling.

Every claim below was actually run and verified during development —
including real bugs found and fixed by testing rather than assumed away.

## What's implemented and verified

| Area | Status | Verified by |
|---|---|---|
| Orchestrator (LangGraph) | ✅ real `StateGraph`, conditional revise/proceed edge, `recursion_limit` backstop, per-agent timing instrumentation | forced the critic to always object — confirmed it loops exactly `max_revision_cycles` times then still completes |
| Data Scientist / Statistical Analyst / Hypothesis / Experiment / ML Experiment / Critic / Report agents | ✅ all real computations (scipy, scikit-learn), never fabricated | `tests/test_pipeline.py` |
| Research Agent — local RAG | ✅ selectable TF-IDF or pgvector retrieval (`RETRIEVAL_BACKEND=auto|tfidf|pgvector`) | TF-IDF is covered against the sample PDF; pgvector dispatch, embedding, and result mapping are unit-tested; live Postgres checks require a running pgvector database |
| **Research Agent — web search** | ✅ real `ddgs`-based implementation (`tools/web_search.py`), tried only when local documents don't already answer the question | code path exercised and confirmed to degrade to an empty list rather than crash, since this build's sandbox network policy can't reach live search engines — **not verified against real search results**; run `python -c "from tools.web_search import search; print(search('test'))"` in an unrestricted environment to confirm |
| Persistence | ✅ SQLite (`database/db.py`) and real PostgreSQL 16 + pgvector 0.6.0 (`database/postgres_db.py`) | tested live: schema creation, insert, fetch, list |
| Multi-user auth | ✅ bcrypt + JWT, per-user data isolation | `tests/test_api.py` — including a real bug found and fixed, see below |
| PDF export | ✅ `fpdf2`-based renderer | `test_pdf_export_returns_valid_pdf`; rendered to page images and visually inspected |
| Live progress streaming | ✅ Server-Sent Events, background thread, per-phase events | consumed the raw stream and confirmed phases arrive incrementally |
| Dataset explorer | ✅ backend endpoint + full Next.js page | tested directly + included in the production build |
| Evidence graph | ✅ custom SVG, hypothesis → evidence links | part of the passing production build |
| **Investigation graph (task decomposition)** | ✅ `web/components/TaskGraph.tsx` — shows which phases actually ran (parsed from the real log, not a static diagram) and how many revision cycles fired | part of the passing production build |
| **Observability / admin view** | ✅ `GET /admin/stats` aggregates real per-agent timing, status breakdown, revision-cycle usage, and critic-finding rate across all stored investigations; `/admin` page visualizes it | `test_admin_stats_aggregates_real_data`: creates 2 real investigations, confirms the aggregate reflects them exactly (not hardcoded) |
| **Visual design** | ✅ deliberate identity, not framework defaults — deep blue-charcoal palette, single brass accent, serif headlines (`Source Serif 4`) + monospace data display (`JetBrains Mono`), both self-hosted via `@fontsource` (no external font CDN calls), sharp instrument-style radii instead of rounded SaaS cards | `npm run build` succeeds; compiled CSS inspected directly to confirm the custom palette and both fonts are actually present, not just declared |
| Evaluation harness | ✅ `evaluations/benchmark.py`, 2 cases against the real pipeline | both pass |
| Python execution | ✅ optional LangGraph tool node, isolated subprocess, timeout, and logged result; API access requires a configured shared API key | `tests/test_pipeline.py` and `tests/test_api.py` |
| Tests | `pytest tests/ -v` | Backend integration tests use SQLite; live Postgres checks require a configured database |

## Bugs found and fixed during this build

1. **Cross-user data leak.** The orchestrator persisted investigations
   before the API layer could attach the requesting user's ID, and the
   upsert's `DO UPDATE` clause never touched `user_id` — every
   investigation was silently saved as unowned, so any authenticated
   user could fetch any other user's report by ID. Fixed by moving
   persistence entirely into the API layer; covered by
   `test_multi_user_investigation_isolation`.
2. **PDF renderer crash on realistic reports.** `fpdf2`'s `multi_cell`
   leaves the cursor at the right edge rather than the left margin,
   so it drifted right across calls until a later line had ~0 width
   and raised `FPDFException`. Only surfaced on a real multi-section
   report. Fixed by explicitly resetting the cursor before every call.
3. **Duplicate JSX attribute.** A scripted color-palette find/replace
   on `EvidenceGraph.tsx` produced two `style` props on the same `<svg>`
   element — caught immediately by `npm run build`'s type check, not
   silently shipped.

## Running it

```bash
pip install -r requirements.txt
python run_demo.py              # LangGraph CLI run, writes reports_out.md
pytest tests/ -v
python evaluations/benchmark.py
uvicorn api:app --reload         # http://127.0.0.1:8000

cd web && npm install && npm run dev   # http://localhost:3000 -- /, /lab, /explorer, /admin
```

Auth, PDF export, live streaming, Postgres, and Docker instructions are
unchanged from before — see inline comments in `api.py`, `.env.example`,
and `docker-compose.yml`.

Set `RETRIEVAL_BACKEND=auto` to use pgvector when `DATABASE_URL` selects
Postgres and TF-IDF with the SQLite fallback. Set `tfidf` or `pgvector` to
force a backend. The `/investigations` request can optionally include
`python_code`; this requires a configured `API_KEY` and an `X-API-Key` header.

## Deploy for free

Verified against each provider's published pricing in September 2026.
All three require no credit card at the free tier used here:

| Piece | Provider | Free tier | Catch |
|---|---|---|---|
| Database | [Neon](https://neon.com) | Permanent, 0.5GB, pgvector included on every plan | Compute suspends after 5 min idle, resumes in ~100ms on next query — not a problem for a demo |
| Backend API | [Render](https://render.com) | 750 instance-hours/month | Sleeps after 15 min idle, ~30-60s cold start on the next request |
| Frontend | [Vercel](https://vercel.com) | Unlimited deploys, 100GB bandwidth/month | Hobby tier license is personal/non-commercial use only |
| CI | GitHub Actions | Unlimited on public repos, 2,000 min/month on private | — |

Steps:

1. **Database**: create a free Neon project, open its SQL editor, run
   `CREATE EXTENSION vector;`, and copy the connection string it gives you.
2. **Backend**: push this repo to GitHub, then in Render choose
   "New +" → "Blueprint" and point it at the repo — `render.yaml` in the
   root configures the service automatically. Set `DATABASE_URL` in
   Render's dashboard to the Neon connection string from step 1.
3. **Frontend**: in Vercel, "Add New" → "Project", import the same repo,
   and set **Root Directory** to `web` (this repo is a monorepo — Vercel
   needs to know the Next.js app isn't at the repo root). Set the env var
   `NEXT_PUBLIC_API_URL` to your Render service's URL.
4. **CI/CD gating** (optional but recommended): in Render, copy the
   service's Deploy Hook URL (Settings → Deploy Hook) and add it as a
   GitHub Actions secret named `RENDER_DEPLOY_HOOK_URL`. Do the same in
   Vercel (Settings → Git → Deploy Hooks) as `VERCEL_DEPLOY_HOOK_URL`.
   With both secrets set, `.github/workflows/ci.yml`'s `deploy` job only
   fires the hooks *after* the test and build jobs pass — so a broken
   push to `main` never reaches production, instead of Render/Vercel's
   default behavior of deploying independently of whether tests pass.
   Without these secrets, the workflow still runs tests on every push;
   it just skips the deploy step and says so in the log.

The project uses local Ollama llama3 as its only LLM provider. Install Ollama
and run `ollama pull llama3`. Start the Ollama service, then run the API
The project uses local Ollama llama3 as its only LLM provider. Install Ollama
and run `ollama pull llama3`. Start the Ollama service, then run the API
locally; it connects to `http://localhost:11434` by default.
`POST /ollama-query` accepts
`{"prompt": "Why did revenue decrease?"}`. `POST /chatbot` accepts a prompt
and optionally the `conversation_id` returned from a previous turn. After an
investigation finishes on `/lab`, the report discussion panel sends the report,
hypotheses, and critique as context to Ollama and keeps follow-up turns in the
same conversation. Its prompt starters cover findings, marketing what-ifs,
analysis improvements, and competitor research. The enhanced PDF export
includes descriptive statistics, customer cohorts, bar/pie/line/scatter charts
including an explicitly non-causal trend line), and Ollama findings. Send one
of `dataset_path`, `dataset_json` (a list of records or column mapping), or
`csv_data` to `POST /generate-report`, for example:
`{"csv_data":"region,revenue\nEast,120\nWest,95"}`.
If Ollama is unavailable, the PDF still includes the deterministic analysis
and an explanation that AI findings could not be generated. Investigation
markdown synthesis can also be enabled with `OLLAMA_REPORTS=true`. In Docker
Compose, host Ollama is reached at `host.docker.internal:11434`; set
`OLLAMA_BASE_URL` to override it.

## Architecture

```
Next.js (web/)  ->  FastAPI (api.py)  ->  LangGraph orchestrator
   |  /            (landing)             (core/orchestrator_langgraph.py,
   |  /lab         (SSE live stream,      per-agent timing recorded)
   |               task graph, evidence       |
   |               graph, PDF export)     data scientist, researcher (local +
   |  /explorer    (dataset profile)      web search), hypothesis, experiment,
   |  /admin       (observability)        ml_experiment agents run in sequence
                                               |
                                           Critic --- revise? --> loop back (bounded)
                                               |
                                           Report Generator --> Markdown / PDF
                                               |
                       api.py persists (SQLite or Postgres), scoped to user_id
                       core/observability.py aggregates stats for /admin
```

## Honest gaps (not built)

- Web search is implemented but unverified against a live search engine (sandbox network restriction — see table above)
- Real LLM-token/cost tracking in `/admin/stats`
- Admin role/permission system — `/admin/stats` is open to any caller, not gated to actual admins
- Rate limiting, upload size/type validation hardening
- Password reset / email verification flows
- Docker (written, never run — no Docker daemon in this build sandbox)

## Substitutions still in play

- **Embeddings**: real `sentence-transformers` if it can download weights, otherwise a
  deterministic hash embedding (`tools/embeddings.py`)
- **Hypothesis generation**: statistical hypotheses remain evidence-derived; the optional
   LLM writes sales experiments, not unverified statistical claims
