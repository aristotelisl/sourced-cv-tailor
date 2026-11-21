# CLAUDE.md

This repo is **CV Tailor**, a local tool for tailoring a CV to job listings.
Read `SPEC.md` before starting any milestone.

## Most important rule
The app must never invent experience. Everything on a CV comes from `data/profile.yaml`.
When you write prompts for the LLM tailoring step, include this rule explicitly and
enforce it in code (validate every bullet's `source` id against the profile). The same
applies to you: don't add facts about the user to `profile.yaml` unless they've told you them.

## Stack
- Backend: Python 3.12, FastAPI, Pydantic v2, Jinja2, Playwright (Chromium), SQLite
- Frontend: React + TypeScript + Vite, Zustand for state, Tailwind + shadcn/ui
- LLM: provider from `.env` (`CV_TAILOR_PROVIDER`): Anthropic SDK (default; Haiku 5.5 for
  analyse/bullet/answer, Sonnet 5.5 for tailor/extras) or any OpenAI-compatible API over httpx
  (`backend/llm/openai_compat.py`). Structured outputs either way; `backend/llm/client.py:parse`
  is the only call site, so keep prompts and checks provider-agnostic.

## Conventions
- Keep `templates/cv.html.j2` visually identical to the current CVs unless asked for a redesign.
- `examples/*.tailored.json` are golden files: keep the renderer compatible with them.
- Tests run against the fictional `examples/profile.example.yaml` (Jordan Avery), never the
  user's own `data/profile.yaml` (git-ignored). Person-specific rules belong in the profile's
  `preferences:` section, not in code or prompts.
- Pydantic models are the single definition of every JSON contract; generate or mirror
  TypeScript types from them, don't hand-maintain two different shapes.
- Work in milestones (SPEC.md §7). After each one, run the tests and render a PDF to check.
- Prefer small, readable modules over clever abstractions.
- Never commit `.env`, generated PDFs under `out/`, or the SQLite database.

## Commands (fill in as the project grows)
- Render an example: `python scripts/render_cv.py examples/example_frontend.tailored.json --out out/`
- Tailor a job end to end (real API calls): `python scripts/tailor_job.py job.txt --out out/ [--accept-suggestions]`
- Start everything (backend + frontend windows, opens browser): double-click `run-cv-tailor.bat` (runs `scripts/start.ps1`)
- Backend dev: `uvicorn backend.main:app --reload`
- Frontend dev: `cd frontend && npm run dev` (open http://localhost:5173; backend must be on :8000)
- Frontend tests/build: `cd frontend && npm test && npm run build`
- After changing a Pydantic model: `cd frontend && npm run gen:types` (regenerates `src/api/schema.ts`)
- Tests: `pytest` (venv: `.venv\Scripts\python -m pytest`)
- Live LLM tests (real API calls, cost money): set `CV_TAILOR_LIVE_TESTS=1` and run `pytest tests/test_analyse_live.py tests/test_tailor_live.py tests/test_polish_live.py tests/test_import_live.py`
- Browser end-to-end (starts both servers on :8100/:5273 with a temp DB and a temp copy of the profile, so your running app is untouched; some scripts call the API): `.venv\Scripts\python tests/e2e/run.py [e2e_tracker.py]`
- Settings: copy `.env.example` to `.env` (`ANTHROPIC_API_KEY`, or `CV_TAILOR_PROVIDER=openai` + `CV_TAILOR_BASE_URL`/`CV_TAILOR_API_KEY`; optional `CV_TAILOR_MODEL[_<STEP>]`, `CV_TAILOR_DB`, `CV_TAILOR_PROFILE`)
- API cost: every model call is logged to the backend console and the `llm_usage` table; summary: `.venv\Scripts\python scripts/usage_report.py [--days 7]`
- First run: the app opens on profile setup (upload a CV, or explore with the sample profile, which copies
  `examples/profile.example.yaml` to `data/profile.yaml`). Saving an imported profile over one of your own backs it
  up as `data/profile.backup-<date>.yaml` (git-ignored)
- Answering gap-report questions in the app edits `data/profile.yaml` (typed edits, previewed as a diff, applied with ruamel so comments survive)
- Tracker database: `data/cv_tailor.db` (SQLite, git-ignored; created on first use; tests use a temp file)
