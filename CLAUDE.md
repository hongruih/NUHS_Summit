# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the App

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
- `PORT` — port the app listens on (default: `5001`; set automatically by Render/Railway)
- `DATABASE_PATH` — path to the SQLite file (default: `booth_data.db`; set to e.g. `/data/booth_data.db` on Render with a persistent disk)
- `FLASK_DEBUG` — set to `true` for local development only

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
- `landing.html` — participant landing page with 3 survey cards (rendered at `/`)
- `admin.html` — main 6-tab admin dashboard (rendered at `/admin`)
- `survey_turing.html` — mobile Turing test survey (rendered at `/survey/turing`)
- `survey_sentiment.html` — sentiment survey stub (rendered at `/survey/sentiment`)
- `survey_acceptance.html` — AI acceptance survey stub (rendered at `/survey/acceptance`)

## Routes

| Route | Purpose |
|---|---|
| `GET /` | Participant landing page — 3 survey cards |
| `GET /admin` | Main 6-tab dashboard (staff-facing) |
| `GET /survey` | Redirects to `/survey/turing` |
| `GET /survey/turing` | Mobile-friendly Turing test survey (attendee-facing, QR-accessible) |
| `GET /survey/sentiment` | Sentiment survey (stub — Step 5) |
| `GET /survey/acceptance` | AI Acceptance Survey (stub — Step 7) |
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

## Active Refactor — Implementation Plan Status

A major refactor is in progress. Steps are being implemented sequentially; each is independently testable before proceeding to the next.

| Step | Description | Status |
|------|-------------|--------|
| 1 | Infrastructure: `requirements.txt`, env vars (`PORT`, `DATABASE_PATH`, `FLASK_DEBUG`), `.env.example` | ✅ Done |
| 2 | Refactor templates into `templates/` directory; routes use `render_template()` | ✅ Done |
| 3 | Add AI Acceptance Survey DB table (`acceptance_responses`) and API endpoints (`POST /api/acceptance/submit`, `GET /api/acceptance/stats`) | ✅ Done |
| 4 | Participant landing page at `/`; admin moves to `/admin`; routing split for all survey URLs | ✅ Done |
| 5 | Sentiment survey: sequential participant flow, 4 questions, no word cloud | ✅ Done |
| 6 | Completion modal — skipped (not appropriate for single-survey completion) | Skipped |
| 7 | AI Acceptance Survey Part A (biographical, multi/single-select) | ✅ Done |
| 8 | AI Acceptance Survey Parts B–F (Likert scale, 41 questions) | ✅ Done |
| 9 | Admin dashboard: integrate AI Acceptance Survey metrics | ✅ Done |
| 10 | Admin: expandable/modal views for all metric cards | ✅ Done |
| 11 | Admin: Turing Test filter by job group | Next |
| 12 | Excel export (`GET /api/export/excel`, 3-sheet `.xlsx`) | — |
| 13 | Turing Test: add completion modal | — |
| 14 | Vibrant design refresh, logo placeholder, credit line | — |
| 15 | Mobile responsiveness audit across all templates | — |
