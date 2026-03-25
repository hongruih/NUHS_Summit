# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the App

**Production (Gunicorn):**
```bash
source venv/bin/activate
gunicorn app:app --bind 0.0.0.0:5001
# Open http://localhost:5001
```

**Local dev (Flask built-in server):**
```bash
source venv/bin/activate
python app.py
# Open http://localhost:5001
```

Install dependencies (first time or after reset):
```bash
pip install -r requirements.txt
```

Environment variables (copy `.env.example` to `.env` for local dev):
- `PORT` — port the app listens on (default: `5001`; set automatically by Render/Railway); pass to Gunicorn via `--bind 0.0.0.0:$PORT`
- `DATABASE_PATH` — path to the SQLite file (default: `booth_data.db`; set to e.g. `/data/booth_data.db` on Render with a persistent disk)
- `FLASK_DEBUG` — set to `true` for local development only (has no effect under Gunicorn)

There is no build step, test suite, or linter configured.

## Architecture

`app.py` (~650 lines) contains all routes and business logic. HTML lives in `templates/`.

**Data persistence**: SQLite via `booth_data.db` (path overridable via `DATABASE_PATH` env var; auto-created on startup by `init_db()`).

**Key in-file sections** (separated by banner comments):
- Lines ~47–128: Configuration — `QUESTIONS`, `STOP_WORDS`, `SCENARIOS` (Turing test clinical cases), `JOB_GROUPS`, `SENIORITY_LEVELS`, `TRUST_TASKS`, `ACCEPTANCE_PART_A`, `ACCEPTANCE_LIKERT`
- Lines ~135–200: Database setup (`get_db`, `init_db`) — creates 5 tables: `sentiment_responses`, `turing_responses`, `turing_answers`, `turing_tasks`, `acceptance_responses`
- Lines ~200–320: Business logic — `sentiment()` (TextBlob), `extract_words()` (word frequency), `get_turing_stats()` (analytics aggregations)
- Lines ~320–650: Flask routes

**Templates** (`templates/`):
- `landing.html` — participant landing page with 3 survey cards (rendered at `/`); clicking "AI Perspectives" opens an instruction modal before navigating
- `admin.html` — main 6-tab admin dashboard (rendered at `/admin`)
- `survey_turing.html` — mobile Turing test survey (rendered at `/survey/turing`)
- `survey_sentiment.html` — sentiment survey (rendered at `/survey/sentiment`)
- `survey_acceptance.html` — AI acceptance survey (rendered at `/survey/acceptance`)

**Design system**: All templates use a Google-inspired light theme — white (`#ffffff`) / light grey (`#f1f3f4`) backgrounds, `#202124` primary text, `#5f6368` secondary text, `#dadce0` borders. Accent colours (indigo `#4f46e5`/`#6366f1`, pink `#ec4899`, purple `#a855f7`, cyan `#06b6d4`) are used for buttons, highlights, and gradients. Do not introduce dark backgrounds or light-on-dark text.

## Routes

| Route | Purpose |
|---|---|
| `GET /` | Participant landing page — 3 survey cards |
| `GET /admin` | Main 6-tab dashboard (staff-facing) |
| `GET /survey` | Redirects to `/survey/turing` |
| `GET /survey/turing` | Mobile-friendly Turing test survey (attendee-facing, QR-accessible) |
| `GET /survey/sentiment` | Sentiment survey |
| `GET /survey/acceptance` | AI Acceptance Survey |
| `GET /qr` | Generates PNG QR code pointing to `/survey/turing` |
| `POST /api/submit` | Submit a sentiment response (JSON: `text`, `question_index`) |
| `GET /api/q/<int:q>` | Word cloud + stats for question index 0–2 |
| `GET /api/all` | Aggregate data for all questions + Turing snapshot |
| `POST /api/turing/submit` | Submit a completed Turing test survey |
| `GET /api/turing/stats` | Full Turing test analytics |
| `GET /api/turing/scenarios` | Scenarios without AI labels (used by survey form) |
| `POST /api/acceptance/submit` | Submit AI Acceptance Survey (JSON: Part A fields + `likert_answers`) |
| `GET /api/acceptance/stats` | AI Acceptance Survey analytics (Part A distributions + Likert averages) |
| `POST /api/reset` | Wipe all data from all tables (incl. acceptance_responses) |
| `GET /api/export` | Export all data as JSON (incl. acceptance stats) |

## Admin Dashboard Tabs (current)

1. **Live Overview** — aggregate word cloud + sentiment + Turing snapshot
2–4. **Q1/Q2/Q3 Input** — record/type responses per question, per-question dashboard
5. **Per-Q Dashboard** — all 3 questions' word clouds and sentiments side-by-side
6. **AI vs Human** — Turing test survey UI + live results dashboard

## Data Model Notes

- `sentiment_responses`: stores free-text audience responses with pre-computed TextBlob polarity/subjectivity/label
- `turing_responses`: one row per survey respondent (UUID, job group, seniority)
- `turing_answers`: one row per scenario per respondent (guess, correctness, 4 ratings 1–5)
- `turing_tasks`: which AI tasks each respondent trusts (multi-select)
- `acceptance_responses`: one row per respondent — Part A fields as individual columns; `disciplines` and `ai_tools` stored as JSON arrays; `likert_answers` stored as JSON object `{"B1": 3, ..., "F7": 5}` covering all 41 questions across Parts B–F
- The `ai_index` field in `SCENARIOS` (0 or 1) indicates which response is AI-generated; this is never exposed to the survey frontend

## Completed Work

All planned refactor steps are done. Post-refactor additions:

| # | Description | Status |
|---|-------------|--------|
| 1 | Infrastructure: `requirements.txt`, env vars, `.env.example` | ✅ Done |
| 2 | Templates directory; `render_template()` throughout | ✅ Done |
| 3 | AI Acceptance Survey DB table + API endpoints | ✅ Done |
| 4 | Participant landing page `/`; admin at `/admin`; survey routing | ✅ Done |
| 5 | Sentiment survey: sequential flow, 3 questions, mic + type input | ✅ Done |
| 6 | Completion modal — skipped | Skipped |
| 7 | AI Acceptance Survey Part A (biographical) | ✅ Done |
| 8 | AI Acceptance Survey Parts B–F (Likert, 41 questions) | ✅ Done |
| 9 | Admin: AI Acceptance metrics tab | ✅ Done |
| 10 | Admin: expandable/modal views for all metric cards | ✅ Done |
| 11 | Admin: Turing Test filter by job group | ✅ Done |
| 12 | Excel export — `GET /api/export/excel`, 3-sheet `.xlsx`, wide-format pivot | ✅ Done |
| 13 | Turing Test: completion modal | — (not implemented) |
| 14 | Design refresh: logo, credit line, animated landing page | ✅ Done |
| 15 | Mobile responsiveness audit across all templates | ✅ Done |
| 16 | Light theme (Google-inspired) across all 5 templates | ✅ Done |
| 17 | Landing page: instruction modal before AI Perspectives survey | ✅ Done |
