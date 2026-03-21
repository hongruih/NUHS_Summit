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
pip install flask textblob qrcode pillow
```

There is no build step, test suite, or linter configured.

## Architecture

The entire application is a **single file**: `app.py`. There are no separate templates, static files, or modules.

**Data persistence**: SQLite via `booth_data.db` (auto-created on startup by `init_db()`).

**Key in-file sections** (separated by banner comments):
- Lines ~46–127: Configuration — `QUESTIONS`, `STOP_WORDS`, `SCENARIOS` (Turing test clinical cases), `JOB_GROUPS`, `SENIORITY_LEVELS`, `TRUST_TASKS`
- Lines ~134–183: Database setup (`get_db`, `init_db`) — creates 4 tables: `sentiment_responses`, `turing_responses`, `turing_answers`, `turing_tasks`
- Lines ~190–303: Business logic — `sentiment()` (TextBlob), `extract_words()` (word frequency), `get_turing_stats()` (analytics aggregations)
- Lines ~309–476: Flask routes
- Lines ~482+: HTML templates as Python strings (`TMPL` for the main dashboard, `SURVEY_TMPL` for the mobile survey page)

## Routes

| Route | Purpose |
|---|---|
| `GET /` | Main 6-tab dashboard (staff-facing) |
| `GET /survey` | Mobile-friendly Turing test survey (attendee-facing, QR-accessible) |
| `GET /qr` | Generates PNG QR code pointing to `/survey` |
| `POST /api/submit` | Submit a sentiment response (JSON: `text`, `question_index`) |
| `GET /api/q/<int:q>` | Word cloud + stats for question index 0–2 |
| `GET /api/all` | Aggregate data for all questions + Turing snapshot |
| `POST /api/turing/submit` | Submit a completed Turing test survey |
| `GET /api/turing/stats` | Full Turing test analytics |
| `GET /api/turing/scenarios` | Scenarios without AI labels (used by survey form) |
| `POST /api/reset` | Wipe all data from all tables |
| `GET /api/export` | Export all data as JSON |

## Dashboard Tabs

1. **Live Overview** — aggregate word cloud + sentiment + Turing snapshot
2–4. **Q1/Q2/Q3 Input** — record/type responses per question, per-question dashboard
5. **Per-Q Dashboard** — all 3 questions' word clouds and sentiments side-by-side
6. **AI vs Human** — Turing test survey UI + live results dashboard

## Data Model Notes

- `sentiment_responses`: stores free-text audience responses with pre-computed TextBlob polarity/subjectivity/label
- `turing_responses`: one row per survey respondent (UUID, job group, seniority)
- `turing_answers`: one row per scenario per respondent (guess, correctness, 4 ratings 1–5)
- `turing_tasks`: which AI tasks each respondent trusts (multi-select)
- The `ai_index` field in `SCENARIOS` (0 or 1) indicates which response is AI-generated; this is never exposed to the survey frontend
