# CV Tailor: Product Spec

A local web app that turns your master profile and a job listing into a tailored,
one-page CV PDF, plus the short texts that go with an application. It automates
the process of tailoring by hand: paste a job, get a CV matched to it, see what's
missing, fix it, export.

Single user, runs locally with your own API key. No accounts, no multi-tenancy.

---

## 1. The workflow it automates

1. **Paste a job listing** (text or URL).
2. **Analyse it** into structured requirements: must-haves, nice-to-haves, stack,
   seniority, location, salary, right-to-work rules, and the keywords that matter.
3. **Tailor the CV** from `data/profile.yaml` only:
   - choose section order (e.g. Education first for new-grad roles, Employment first otherwise)
   - choose and rephrase bullets for each job, project and award
   - reorder and regroup skills so the job's stack comes first
   - choose header extras (e.g. a right-to-work line for roles in a given country)
4. **Gap report**: missing must-haves, missing nice-to-haves, unverified facts used,
   questions to answer, and red flags (salary currency suggests another country,
   on-site location, years-of-experience mismatch, visa rules).
5. **Review and edit** in the UI with a live preview; accept, edit or regenerate each bullet.
6. **Export** a one-page PDF (auto-tightens the layout if it overflows).
7. **Extras on demand**: cover letter, "tell us about yourself" blurb, recruiter or
   referral message, salary-research notes.
8. **Track** every application: company, role, date, status, CV version, notes.

---

## 2. Hard rules (non-negotiable)

- **No invented experience.** Every bullet must trace to a `source` id in `profile.yaml`.
  Rephrasing and reframing is fine; adding a technology, metric, responsibility or
  result that isn't in the profile is not.
- **Unverified facts are flagged**, never silently used. Items with `verified: false`
  or listed under `unconfirmed` must show a warning badge in the UI and appear in
  the gap report.
- **Skills in `not_claimed` are never added.** If a job needs one, it goes in the gap report.
- **One page, A4.** Fit by layout steps first; if it still overflows, ask which bullet to cut.
- **Header extras are opt-in.** Never add "EU Citizen" unless I tick it.
- **Secrets stay local.** The API key lives in `.env`, which is git-ignored.

---

## 3. Architecture

```
frontend/   React + TypeScript + Vite + Zustand + Tailwind (+ shadcn/ui)
backend/    Python + FastAPI + Pydantic
            ├─ llm/        model calls (Claude or OpenAI-compatible) with structured (JSON schema) outputs
            ├─ render/     Jinja2 template → HTML → Playwright → PDF (from scripts/render_cv.py)
            └─ store/      SQLite (applications, CV versions, job analyses)
data/       profile.yaml (source of truth, edited by me)
templates/  cv.html.j2  (the CV design; matches the PDFs I've been sending)
examples/   golden tailored JSONs used as few-shot examples and regression tests
```

- **LLM:** Claude via the official Anthropic SDK by default, or any OpenAI-compatible API (OpenAI, Gemini, OpenRouter, Ollama...), with structured outputs
  (tool use / JSON schema) validated by Pydantic. Model name configurable in `.env`.
- **PDF:** reuse `scripts/render_cv.py` logic (Playwright Chromium, page-count check, fit steps).
- **Storage:** SQLite via SQLModel or plain sqlite3. Store each tailored CV JSON so any
  version can be re-rendered.
- **Run:** `docker compose up`, or two dev servers with a Vite proxy to `/api`.

---

## 4. Data contracts

### 4.1 Job analysis (LLM output)
```json
{
  "company": "Stripe", "title": "Software Engineer, New Grad - Frontend",
  "location": "Barcelona, on-site 50%", "remote": "hybrid",
  "salary": {"min": 46200, "max": 69400, "currency": "EUR", "period": "year"},
  "seniority": "new-grad", "years_required": "0-1.5",
  "must_have": ["CS degree", "programming experience", "multi-person projects", "AI tools with critical review"],
  "nice_to_have": ["frontend specialisation", "code review", "large codebases"],
  "stack": ["Java", "Ruby", "JavaScript", "Scala", "Go"],
  "right_to_work": "Spain (EU)",
  "keywords": ["frontend", "React", "large codebases", "AI-assisted development"],
  "role_family": "frontend"
}
```
`role_family` is one of: frontend, fullstack, backend, ai-engineer, data, quant, systems, other.

### 4.2 Tailored CV (LLM output → renderer input)
See `examples/example_frontend.tailored.json`. Key fields:
- `sections[]`: `title`, `entries[]` (`source`, `left`, `middle`/`middle_url`…, `right`, `bullets[]`), optional `skills[]`
- every bullet has `text`, optional `tech`, and `source` (profile bullet id, `+`-joined if merged)
- `header_extras[]`, `filename`, `layout` overrides
- `gap_report`: `must_have_missing`, `nice_to_have_missing`, `unverified_used`, `questions`, `flags`

### 4.3 Application record
`id, company, title, url, location, salary, status (draft|applied|interview|offer|rejected|on-hold), applied_at, cv_version_id, notes, contacts`

---

## 5. Tailoring heuristics (defaults; the profile's `preferences` override them)

| Role family | Section order | Lead with |
|---|---|---|
| frontend / fullstack (experienced) | Employment, Education, Project, Awards, Skills | Next.js/TS dashboard, React Flow editor, state management |
| new-grad / graduate | Education first | Degree, then experience, collaboration, learning codebases |
| backend-heavy fullstack | Employment first | Python microservices, integrations, Flask/FastAPI pipeline |
| AI engineer / AI solutions | Employment first | Production LLM work, structured outputs, validation, Claude Code |
| data engineering | Education first | Unstructured → structured pipeline, data quality checks, APIs, SQL |
| quant / finance | Education first | Python, validation framework, ML evaluation; flag missing risk/pricing |
| systems / performance | Education first | Agentic AI + RAG, C++/Python, Linux, Docker; flag missing profiling |

Other rules:
- Header lines are suggested from `preferences.header_suggestions` (e.g. a UK right-to-work line for UK roles).
- Right to work, on-site location and salary currency are checked against `preferences`
  (`work_rights`, `home_places`, `home_currencies`); a check is skipped when its key is missing.
- `preferences.tailoring_notes` is free text the tailoring prompt follows (section order, what to lead with, length).
- Salary in an unexpected currency (e.g. INR) → flag "posting is probably for another country".
- The job's languages and frameworks go first in Skills, but only if they're in `strong` or `listed`.
- Keep the dissertation as the "Selected Project"; reframe its bullets for the role family.
- Don't use a "Profile" summary section.

---

## 6. UI

1. **New application**: paste the job text or URL → "Analyse".
2. **Analysis panel**: extracted requirements as chips (green = covered, amber = partial,
   red = missing) and red flags.
3. **Editor**: left = section/bullet list (drag to reorder, edit inline, regenerate one
   bullet, swap in an alternative from the bullet bank, badge for unverified sources);
   right = live A4 preview (iframe of the rendered HTML).
4. **Gap report and questions**: answering a question can append a fact to `profile.yaml`
   (with a diff preview before saving).
5. **Export**: PDF download, page-count indicator, fit step used.
6. **Extras**: cover letter, about-me blurb, message drafts.
7. **Tracker**: table of applications with status, date, and links to CV versions.
8. **Profile editor**: edit `profile.yaml` in a form or raw YAML, with validation.

---

## 7. Milestones

1. **M1: Renderer.** Port `scripts/render_cv.py` into the backend. `POST /api/render`
   (tailored JSON → HTML/PDF). Test: rendering `examples/*.tailored.json` gives 1 page.
2. **M2: Job analysis.** `POST /api/analyse` (text → job analysis JSON). Pydantic-validated.
3. **M3: Tailoring.** `POST /api/tailor` (profile + analysis → tailored CV + gap report).
   Source-id validation runs on every result and rejects unknown ids.
4. **M4: Frontend.** Paste → analyse → tailor → edit → live preview → export.
5. **M5: Tracker and versions** (SQLite).
6. **M6: Extras.** Cover letter, about-me blurb, messages (same no-invention rule).
7. **M7: Polish.** Regenerate a single bullet, bullet-bank swap, answering questions updates the profile.

## 8. Acceptance tests

- Rendering the golden example gives 1 page with the same sections.
- Tailoring for a backend-heavy job never invents Kubernetes/AWS; they appear in `nice_to_have_missing` / `must_have_missing`.
- A job with salary in INR gets a "probably another country" flag.
- A UK job gets the UK header suggestion configured in `preferences`; a job elsewhere doesn't.
- Any bullet whose `source` isn't in the profile is rejected before rendering.
