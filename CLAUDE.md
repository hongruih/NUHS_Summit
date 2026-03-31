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

> **TextBlob corpora** — on first run TextBlob may need its punkt tokeniser. If you see a corpus error, run:
> ```bash
> python -m textblob.download_corpora
> ```

> **spaCy model** — `pip install -r requirements.txt` installs the spaCy library but **not** the language model, which must be downloaded separately:
> ```bash
> python -m spacy download en_core_web_sm
> ```
> The app runs without it (graceful fallback to the original Counter-based word counting), but spaCy is required for lemmatised, POS-filtered word clouds.

> **better-profanity** — included in `requirements.txt`; no extra setup needed. Initialised at startup via `profanity.load_censor_words()`. Screens submissions at `POST /api/submit` and filters word cloud output in `extract_words()`.

Environment variables (copy `.env.example` to `.env` for local dev):
- `PORT` — port the app listens on (default: `5001`; set automatically by Render/Railway); pass to Gunicorn via `--bind 0.0.0.0:$PORT`
- `DATABASE_PATH` — path to the SQLite file (default: `booth_data.db`; set to e.g. `/data/booth_data.db` on Render with a persistent disk)
- `FLASK_DEBUG` — set to `true` for local development only (has no effect under Gunicorn)

**Render deployment**: There is no `render.yaml` in this repo — this is intentional. Deployment is configured directly in the Render dashboard:
- **Build command**: `pip install -r requirements.txt && python -m spacy download en_core_web_sm`
- **Start command**: `gunicorn app:app --bind 0.0.0.0:$PORT`

## Architecture

`app.py` (~887 lines) contains all routes and business logic. HTML lives in `templates/`.

**Data persistence**: SQLite via `booth_data.db` (path overridable via `DATABASE_PATH` env var; auto-created on startup by `init_db()`). WAL mode enabled (`PRAGMA journal_mode=WAL`) for concurrent read performance under Gunicorn.

**Key in-file sections** (separated by banner comments):
- Lines ~47–128: Configuration — `QUESTIONS` (4 open-ended questions), `STOP_WORDS`, `SCENARIOS` (5 Turing test clinical cases), `JOB_GROUPS`, `SENIORITY_LEVELS`, `TRUST_TASKS`, `ACCEPTANCE_PART_A` (8 fields: age group, gender, cluster, disciplines, years in healthcare, years in role, AI frequency, AI tools — seniority is dynamic in the template), `ACCEPTANCE_LIKERT` (22 Likert questions across Parts B–D with `[discipline]` placeholder substituted client-side)
- Lines ~134–299: Database setup (`get_db`, `init_db`) — creates 5 tables: `sentiment_responses`, `turing_responses`, `turing_answers`, `turing_tasks`, `acceptance_responses`; runs safe `ALTER TABLE` migrations to add `participant_id` to `sentiment_responses`, and `cluster` + `open_reflection` to `acceptance_responses`
- Lines ~301–457: Business logic — `sentiment()` (TextBlob polarity/subjectivity), `extract_words()` (spaCy lemmatisation + NOUN/VERB/ADJ POS filter + merged stop words + `better-profanity` filter → top 80 words; falls back to regex Counter if spaCy unavailable, profanity filter applies in both paths), `get_turing_stats()` (full analytics with optional job-group filter)
- Lines ~460–887: Flask routes — participant pages, admin, all API endpoints, Excel export

**Templates** (`templates/`):
- `landing.html` — participant landing page; 3 survey cards in order: AI vs Human → AI Perspectives → AI Acceptance Survey; clicking "AI Perspectives" opens an instruction modal before navigating; mobile-scroll-safe (no `overflow:hidden` on body, `justify-content:flex-start` on small screens with safe-area bottom padding)
- `admin.html` — 7-tab admin dashboard (rendered at `/admin`); status bar at top shows Total / AI vs Human / AI Perspectives / AI Acceptance counts; tabs split into left group (Live Overview, Q1–Q3 Input) and right group (AI vs Human, AI Perspectives, AI Acceptance) separated by `margin-left:auto` on the `.tab.tt` class
- `survey_turing.html` — mobile Turing test survey (rendered at `/survey/turing`); "Other" job group selection reveals an inline free-text input; combined value saved as `"Other; <custom text>"`
- `survey_sentiment.html` — sentiment survey with microphone + text input (rendered at `/survey/sentiment`); polarity score is calculated and stored but **not displayed** to participants — only the sentiment label (Positive/Neutral/Negative) and polarity bar are shown
- `survey_acceptance.html` — AI acceptance survey (rendered at `/survey/acceptance`); first screen is a consent/intro step (anonymous notice + HCRD research consent); clicking "Begin Survey" proceeds to the 13-step question flow (9 Part A biographical + 3 Likert parts B–D + 1 Part G open reflection); completion screen shows a gift booth message with confetti animation; Part A has two free-text-revealing fields: cluster ("Others") and discipline ("Other"); seniority options (Q5) are dynamic — rendered from a JS `SENIORITY_BY_DISCIPLINE` lookup map keyed by the selected discipline; Likert questions containing `[discipline]` are substituted client-side via `applyDisciplineWord()` using the respondent's chosen discipline; Part G has 4 optional open-ended textarea questions

**Design system**: All templates use a Google-inspired light theme — white (`#ffffff`) / light grey (`#f1f3f4`) backgrounds, `#202124` primary text, `#5f6368` secondary text, `#dadce0` borders. Accent colours (indigo `#4f46e5`/`#6366f1`, pink `#ec4899`, purple `#a855f7`, cyan `#06b6d4`) are used for buttons, highlights, and gradients. Do not introduce dark backgrounds or light-on-dark text.

## Routes

| Route | Purpose |
|---|---|
| `GET /` | Participant landing page — 3 survey cards |
| `GET /admin` | Main 7-tab dashboard (staff-facing) |
| `GET /survey` | Redirects to `/survey/turing` |
| `GET /survey/turing` | Mobile-friendly Turing test survey (attendee-facing, QR-accessible) |
| `GET /survey/sentiment` | AI Perspectives sentiment survey |
| `GET /survey/acceptance` | AI Acceptance Survey |
| `GET /qr` | Generates PNG QR code pointing to `/survey/turing` |
| `POST /api/submit` | Submit a sentiment response (JSON: `text`, `question_index`, optional `participant_id`); returns 400 `{"error": "Inappropriate content"}` if profanity detected — nothing written to DB |
| `GET /api/q/<int:q>` | Word cloud + stats for question index 0–3 |
| `GET /api/all` | Aggregate data for all questions + Turing snapshot |
| `POST /api/turing/submit` | Submit a completed Turing test survey |
| `GET /api/turing/stats` | Full Turing test analytics (optional `?job_group=` filter) |
| `GET /api/turing/scenarios` | Scenarios without AI labels (used by survey form) |
| `POST /api/acceptance/submit` | Submit AI Acceptance Survey (JSON: Part A fields including `cluster` + `likert_answers` + `open_reflection`) |
| `GET /api/acceptance/stats` | AI Acceptance Survey analytics (Part A distributions + Likert averages) |
| `POST /api/reset` | Wipe all data from all tables (incl. acceptance_responses) |
| `GET /api/export` | Export all data as JSON (incl. acceptance stats) |
| `GET /api/export/excel` | Download 3-sheet `.xlsx` export |

## Admin Dashboard Tabs (current)

The admin nav bar has **7 tabs** split into two visual groups (separated by `margin-left:auto` on `.tab.tt`):

**Left group:**
1. **Live Overview** (📊) — aggregate word cloud + sentiment + Turing snapshot; auto-refreshes every 10 s
2. **Q1 Input** — record/type Q1 responses; per-question word cloud and sentiment
3. **Q2 Input** — same for Q2
4. **Q3 Input** — same for Q3

**Right group (right-aligned):**
5. **AI vs Human** (🤖, pink) — Turing test live results: accuracy by job group/seniority/scenario, ratings, task trust chart; filterable by job group
6. **AI Perspectives** (💬, cyan) — all 3 questions' word clouds and sentiments side-by-side
7. **AI Acceptance** (📋, purple) — Part A demographic distributions + Parts B–D Likert averages

**Status bar** (top-right of header): four pills in order — Total responses | AI vs Human count | AI Perspectives count | AI Acceptance count. Counts sourced from: AI vs Human = `turing_responses` row count; AI Perspectives = `sentiment_responses` rows for `question_index=0` (i.e. unique participants who answered at least Q1); AI Acceptance = `/api/acceptance/stats` `total_respondents`. Total = sum of all three.

## Data Model Notes

- `sentiment_responses`: stores free-text audience responses with pre-computed TextBlob polarity/subjectivity/label; `participant_id` column added via safe `ALTER TABLE` migration
- `turing_responses`: one row per survey respondent (UUID, job group, seniority); `job_group` may be `"Other; <custom text>"` when participant selected "Other" and typed a description
- `turing_answers`: one row per scenario per respondent (guess, correctness, 4 ratings 1–5)
- `turing_tasks`: which AI tasks each respondent trusts (multi-select; one row per task)
- `acceptance_responses`: one row per respondent — Part A fields as individual columns; `cluster` stores the selected healthcare cluster (plain text; "Others; <text>" for free-text entry); `disciplines` stored as a single-element JSON array (single-select; "Other" saves as `["Other; <role>"]`); `seniority` stores the full branched tier label (e.g. `"Student (Medical Student)"`); `ai_tools` stored as a JSON array (multi-select); `likert_answers` stored as JSON object `{"B1": 3, ..., "D7": 5}` covering all 22 questions across Parts B–D; `open_reflection` stored as JSON object `{"G1": "...", "G2": "...", "G3": "...", "G4": "..."}` (all optional)
- The `ai_index` field in `SCENARIOS` (0 or 1) indicates which response is AI-generated; this is **never** exposed to the survey frontend

## Completed Work

All planned refactor steps are done. Post-refactor additions:

| # | Description | Status |
|---|-------------|--------|
| 1 | Infrastructure: `requirements.txt`, env vars, `.env.example` | ✅ Done |
| 2 | Templates directory; `render_template()` throughout | ✅ Done |
| 3 | AI Acceptance Survey DB table + API endpoints | ✅ Done |
| 4 | Participant landing page `/`; admin at `/admin`; survey routing | ✅ Done |
| 5 | Sentiment survey: sequential flow, 4 questions, mic + type input | ✅ Done |
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
| 18 | AI Acceptance Survey: consent/intro screen as step 0 | ✅ Done |
| 19 | Landing page: survey card order changed to AI vs Human → AI Perspectives → AI Acceptance Survey | ✅ Done |
| 20 | Landing page: mobile scroll fix — removed `overflow:hidden`, added mobile media query with `justify-content:flex-start` and safe-area bottom padding | ✅ Done |
| 21 | Logo size tuned across all 5 templates (inline `height` on `<img>` only) | ✅ Done |
| 22 | Turing test: "Other" job group shows inline free-text input; saves as `"Other; <text>"` | ✅ Done |
| 23 | AI Perspectives survey: polarity score removed from participant-facing result pop-up (still calculated and stored) | ✅ Done |
| 24 | AI Acceptance completion screen: gift booth message + confetti animation (canvas-based, 60 particles, 3.2 s fade) | ✅ Done |
| 25 | Admin status bar: fixed acceptance count (was always 0); replaced "Ready" pill with AI Perspectives count; fixed total to sum all 3 surveys; reordered pills to Total → Turing → Perspectives → Acceptance | ✅ Done |
| 26 | Admin status bar: AI Perspectives count fixed to use `d['0'].stats.total` (Q1 response count = unique participants) instead of aggregate row sum | ✅ Done |
| 27 | Admin tabs: renamed "Per-Question Dashboard" → "💬 AI Perspectives"; reordered right group to AI vs Human → AI Perspectives → AI Acceptance | ✅ Done |
| 28 | Admin tabs: restored right-alignment by moving `margin-left:auto` from `.tab.dt` to `.tab.tt`; colour-coded AI Perspectives tab with `var(--cy)` to match status bar pill | ✅ Done |
| 29 | Profanity filter (`better-profanity`): blocks submission at `POST /api/submit` (returns 400 if detected); excludes profane lemmas/words from word cloud output in `extract_words()` | ✅ Done |
| 30 | spaCy-based `extract_words()`: lemmatisation + NOUN/VERB/ADJ POS filter + merged stop words; graceful fallback to Counter if spaCy unavailable | ✅ Done |
| 31 | Admin dashboard poll interval changed from 3 s to 10 s (`setInterval` in `admin.html`); UI labels updated to match | ✅ Done |
| 32 | AI Acceptance Survey Part A Q3 (discipline): changed to single-select; "Other" reveals inline free-text input; stored as `"Other; <role>"` in the `disciplines` JSON array; empty "Other" blocked with validation message | ✅ Done |
| 33 | AI Acceptance Survey redesigned: Part A expanded to 9 questions (added cluster Q3, dynamic seniority Q5); Likert replaced with new Parts B–D (22 questions, `[discipline]` substituted client-side); Part G added (4 optional open-ended questions); DB schema updated with `cluster` and `open_reflection` columns; Excel export updated to include new fields | ✅ Done |
