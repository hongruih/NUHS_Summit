# NUHS Summit — AI Surveys App

An interactive, real-time audience engagement tool built for the NUHS Summit 2026. Runs three concurrent surveys — a live sentiment word-cloud booth, an AI-vs-human Turing test, and a structured AI acceptance questionnaire — with a staff-facing admin dashboard and full data export.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Tech Stack](#tech-stack)
3. [Installation](#installation)
4. [Running the App](#running-the-app)
5. [Environment Variables](#environment-variables)
6. [Usage](#usage)
7. [File Structure](#file-structure)
8. [Routes Reference](#routes-reference)
9. [Admin Dashboard](#admin-dashboard)
10. [Data Model](#data-model)
11. [API Reference](#api-reference)
12. [Exporting Data](#exporting-data)
13. [Design System](#design-system)

---

## Project Overview

The app serves two audiences simultaneously:

**Participants (attendees)** access a mobile-friendly landing page at `/` that presents three survey cards:

| Survey | Route | Description |
|---|---|---|
| AI vs Human | `/survey/turing` | 9-step activity: consent → demographics → 3 Scenarios + 2 Conversations (judge whether a response or clinician is human or AI) → trust tasks → results; each item reveals the correct answer inline after submission |
| AI Perspectives | `/survey/sentiment` | Answer 4 open-ended questions about AI in healthcare; responses are transcribed (mic or typed) and analysed for sentiment in real time |
| AI Acceptance Survey | `/survey/acceptance` | 13-step structured survey — 9 biographical questions (Part A, including cluster and branching seniority) + 22 Likert-scale statements across 3 thematic parts (B–D, with discipline-specific wording) + 4 optional open-ended questions (Part G) |

**Staff (admin)** access a 7-tab dashboard at `/admin` that shows live word clouds, sentiment distributions, Turing test accuracy analytics, and AI acceptance metrics. All data persists in SQLite and survives server restarts.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3, Flask |
| Production server | Gunicorn |
| Database | SQLite (WAL mode) via `sqlite3` stdlib |
| Sentiment analysis | TextBlob |
| Word cloud NLP | spaCy `en_core_web_sm` (lemmatisation + POS filter); falls back to `collections.Counter` if unavailable |
| Content moderation | `better-profanity` — blocks profane submissions at the API layer and filters word cloud output |
| QR code generation | `qrcode` + `Pillow` |
| Excel export | `openpyxl` |
| Config | `python-dotenv` |
| Frontend | Vanilla HTML/CSS/JS — no build step, no framework |

---

## Installation

**Prerequisites:** Python 3.9+ and `pip`.

```bash
# 1. Clone or download the repository
cd "NUHS Summit/App"

# 2. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate        # macOS / Linux
# venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy the example env file (edit values as needed)
cp .env.example .env
```

> **TextBlob corpora** — on first run TextBlob may need its punkt tokeniser. If you see a corpus error, run:
> ```bash
> python -m textblob.download_corpora
> ```

> **spaCy model** — `pip install -r requirements.txt` installs the spaCy library but **not** the language model. Download it separately after install:
> ```bash
> python -m spacy download en_core_web_sm
> ```
> The app runs without this (falling back to basic word counting), but the spaCy model is needed for lemmatised, POS-filtered word clouds.

> **better-profanity** — included in `requirements.txt` with no extra setup. Automatically initialised at startup; no action needed after `pip install`.

### Deploying on Render

There is no `render.yaml` in this repo — deployment is configured directly in the **Render dashboard**. When creating the web service, set:

| Setting | Value |
|---|---|
| **Build command** | `pip install -r requirements.txt && python -m spacy download en_core_web_sm` |
| **Start command** | `gunicorn app:app --bind 0.0.0.0:$PORT` |

The build command installs all dependencies and downloads the spaCy language model in one step, so no extra manual action is needed on Render. Set `DATABASE_PATH` to your persistent disk mount path (e.g. `/data/booth_data.db`) in the Render environment variables panel.

---

## Running the App

**Production (Gunicorn — recommended):**
```bash
source venv/bin/activate
gunicorn app:app --bind 0.0.0.0:5001
# Open http://localhost:5001
```

With a custom port (e.g. on Render/Railway where `PORT` is set automatically):
```bash
gunicorn app:app --bind 0.0.0.0:$PORT
```

**Local development (Flask built-in server):**
```bash
source venv/bin/activate
python app.py
# Open http://localhost:5001
```

There is no build step. The database file (`booth_data.db`) is created automatically on first startup.

---

## Environment Variables

Copy `.env.example` to `.env` for local use. On Render/Railway, set these in the hosting dashboard.

| Variable | Default | Description |
|---|---|---|
| `PORT` | `5001` | Port the app listens on. Set automatically by Render/Railway. Pass to Gunicorn via `--bind 0.0.0.0:$PORT`. |
| `DATABASE_PATH` | `booth_data.db` | Path to the SQLite file. On Render with a persistent disk, set to the mount path e.g. `/data/booth_data.db`. |
| `FLASK_DEBUG` | `false` | Set to `true` for local development only. Has no effect under Gunicorn. |

---

## Usage

### As a Participant

1. Navigate to `http://<host>/` on any device (phone, tablet, or desktop).
2. Choose a survey card:
   - **AI vs Human** — read a consent screen, fill in your demographics, then work through 3 Scenarios (single response, judge Human or AI) and 2 Conversations (multi-turn dialog, judge the clinician); after each item you rate quality on trust, empathy, safety, and usefulness, then the correct answer is revealed inline. If your job group is "Other", an inline text field appears to capture your actual role.
   - **AI Perspectives** — tap the mic or type answers to 4 open-ended questions; after each submission, a sentiment result (Positive / Neutral / Negative) is shown.
   - **AI Acceptance Survey** — review the consent/intro screen, then work through 9 biographical questions (including cluster and a discipline-branching seniority picker), 22 Likert statements across Parts B–D (with `[discipline]`-personalised wording), and 4 optional open-ended reflection questions (Part G). On completion, a gift message prompts participants to show the screen at the Healthcare Redesign booth.
3. All surveys are self-paced and fully mobile-responsive.

### As an Admin (Staff)

1. Navigate to `http://<host>/admin`.
2. The header status bar shows live counts: **Total | AI vs Human | AI Perspectives | AI Acceptance**.
3. Use the 7 tabs to monitor live responses, view word clouds, analyse Turing test results, and review acceptance survey distributions.
4. Use the **Reset** button (bottom toolbar) to wipe all data between sessions.
5. Download a full `.xlsx` export from the **Export Excel** button (3-sheet workbook).

### QR Code

A PNG QR code pointing to `/survey/turing` is available at:
```
http://<host>/qr
```
Print or display this at the booth so attendees can scan and go straight to the Turing test survey.

---

## File Structure

```
App/
├── app.py                     # All routes, business logic, and configuration (~887 lines)
├── requirements.txt           # Python dependencies
├── .env.example               # Environment variable template
├── booth_data.db              # SQLite database (auto-created; not committed)
│
├── templates/
│   ├── landing.html           # Participant landing page — 3 survey cards at /
│   ├── admin.html             # 7-tab staff dashboard at /admin
│   ├── survey_turing.html     # AI vs Human Turing test survey at /survey/turing
│   ├── survey_sentiment.html  # AI Perspectives sentiment survey at /survey/sentiment
│   └── survey_acceptance.html # AI Acceptance Survey at /survey/acceptance
│
├── static/
│   ├── HCRD.png               # Organisation logo (displayed in all page headers)
│   └── HCRD2.png              # Alternate logo asset
│
└── venv/                      # Virtual environment (not committed)
```

### Key sections inside `app.py`

| Lines | Section |
|---|---|
| 1–37 | Module docstring and imports |
| 47–68 | `QUESTIONS` (4 open-ended; Q4 uses commas not em dashes) and `STOP_WORDS` |
| 85–215 | `TURING_ITEMS` — 3 Scenarios + 2 Conversations (each with `id`, `section`, `label`, `type`, `is_ai`, `correct_answer`; Scenarios have `patient`/`response`; Conversations have `turns[]`); `JOB_GROUPS`, `SENIORITY_LEVELS`, `TRUST_TASKS`; `ACCEPTANCE_PART_A` (8 fields; seniority is dynamic in JS); `ACCEPTANCE_LIKERT` (Parts B–D, 22 questions with `[discipline]` placeholder) |
| ~220–320 | Database: `get_db()`, `init_db()` — 5 tables + migrations; `turing_answers` auto-migrates to new schema if `item_id` column is absent |
| ~320–360 | Sentiment helpers: `sentiment()`, `extract_words()`, `get_entries()`, `stats_for()` |
| ~360–470 | `get_turing_stats()` — returns `by_item` (per-item accuracy + avg ratings, grouped by section) with optional job-group filter |
| ~470+ | Flask routes (participant pages, admin, all API endpoints, Excel export) |

---

## Routes Reference

### Page routes

| Method | Route | Description |
|---|---|---|
| `GET` | `/` | Participant landing page — 3 survey cards |
| `GET` | `/admin` | Staff admin dashboard (7 tabs) |
| `GET` | `/survey` | Redirects to `/survey/turing` |
| `GET` | `/survey/turing` | AI vs Human Turing test survey |
| `GET` | `/survey/sentiment` | AI Perspectives sentiment survey |
| `GET` | `/survey/acceptance` | AI Acceptance Survey (consent screen + 13 steps) |
| `GET` | `/qr` | QR code PNG pointing to `/survey/turing` |

### API routes

| Method | Route | Description |
|---|---|---|
| `POST` | `/api/submit` | Submit a sentiment response — body: `{text, question_index, participant_id?}`; returns `400` if profanity detected |
| `GET` | `/api/q/<int:q>` | Word cloud + stats + last 15 entries for question index 0–3 |
| `GET` | `/api/all` | All questions' word clouds + sentiment + Turing snapshot |
| `POST` | `/api/turing/submit` | Submit a completed AI vs Human survey — body: `{job_group, seniority, answers[{item_id, section, guess, ratings}], tasks[]}` |
| `GET` | `/api/turing/stats` | Full AI vs Human analytics; optional `?job_group=` filter; returns `by_item` with per-item accuracy and avg ratings |
| `GET` | `/api/turing/scenarios` | Items without `is_ai`/`correct_answer` (safe for external consumers) |
| `POST` | `/api/acceptance/submit` | Submit AI Acceptance Survey — body: `{part_a: {...}, likert_answers: {B1: 3, ...}, open_reflection: {G1: "...", ...}}` |
| `GET` | `/api/acceptance/stats` | Acceptance survey analytics — Part A distributions + Likert averages |
| `POST` | `/api/reset` | Wipe all data from all 5 tables |
| `GET` | `/api/export` | Full JSON export of all data |
| `GET` | `/api/export/excel` | Download 3-sheet `.xlsx` export |

---

## Admin Dashboard

The admin dashboard (`/admin`) has **7 tabs** arranged in two visual groups separated by a natural gap:

**Left group:**

| Tab | Contents |
|---|---|
| **📊 Live Overview** | Aggregate word cloud (all questions), overall sentiment distribution, Turing test snapshot (total respondents, overall accuracy, fooled %), per-question sentiment summary |
| **Q1 Input** | Microphone / text input to record Q1 responses; live word cloud and sentiment panel |
| **Q2 Input** | Same as Q1 Input for Question 2 |
| **Q3 Input** | Same as Q1 Input for Question 3 |

**Right group (right-aligned):**

| Tab | Contents |
|---|---|
| **🤖 AI vs Human** | Live results: hero stats (total respondents, overall accuracy, fooled %), accuracy bars by job group and seniority, **Accuracy by Item** card showing Scenarios and Conversations in separate sub-sections with per-item accuracy and inline avg ratings (Trust/Empathy/Safety/Usefulness), trusted AI tasks chart; filterable by job group |
| **💬 AI Perspectives** | All **4** questions' word clouds and sentiment distributions shown side-by-side |
| **📋 AI Acceptance** | Part A demographic distributions (age, gender, cluster, disciplines, seniority, AI usage frequency, AI tools); Parts B–D Likert question averages with response counts |

**Status bar** (top-right header, 4 pills):

| Pill | Colour | Source |
|---|---|---|
| Total responses | Default | Sum of the three counts below |
| AI vs Human | Pink | `COUNT(*)` from `turing_responses` |
| AI Perspectives | Cyan | `COUNT(*)` from `sentiment_responses` WHERE `question_index = 0` (unique participants who answered at least Q1) |
| AI Acceptance | Purple | `total_respondents` from `/api/acceptance/stats` |

All metric cards are expandable to full-screen modals for presentation use. The dashboard polls all active data every **10 seconds**.

---

## Data Model

Five SQLite tables, all created by `init_db()` on startup:

### `sentiment_responses`
Stores free-text audience responses with pre-computed sentiment.

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | Auto-increment |
| `question_index` | INTEGER | 0–3 (maps to `QUESTIONS` list) |
| `text` | TEXT | Raw response |
| `polarity` | REAL | TextBlob polarity −1.0 to +1.0 |
| `subjectivity` | REAL | TextBlob subjectivity 0.0 to 1.0 |
| `label` | TEXT | `Positive` / `Negative` / `Neutral` |
| `emoji` | TEXT | Display emoji |
| `color` | TEXT | Hex colour for UI |
| `timestamp` | TEXT | ISO 8601 |
| `participant_id` | TEXT | Optional; links responses across questions for the same participant |

### `turing_responses`
One row per Turing test survey respondent.

| Column | Type | Notes |
|---|---|---|
| `respondent_id` | TEXT | Short UUID (8 chars) |
| `job_group` | TEXT | Selected from `JOB_GROUPS`; may be `"Other; <custom text>"` if participant typed a role |
| `seniority` | TEXT | Selected from `SENIORITY_LEVELS` |
| `timestamp` | TEXT | ISO 8601 |

### `turing_answers`
One row per item per respondent (5 rows per survey completion — 3 Scenarios + 2 Conversations).

| Column | Type | Notes |
|---|---|---|
| `respondent_id` | TEXT | FK to `turing_responses` |
| `item_id` | TEXT | e.g. `scenario_1`, `scenario_2`, `scenario_3`, `conversation_1`, `conversation_2` |
| `section` | TEXT | `Scenario` or `Conversation` |
| `guess` | TEXT | `Human Clinician` or `AI` |
| `correct` | INTEGER | 1 if guess matches `correct_answer`, 0 otherwise |
| `rating_trust` | INTEGER | 1–5 |
| `rating_empathy` | INTEGER | 1–5 |
| `rating_safety` | INTEGER | 1–5 |
| `rating_usefulness` | INTEGER | 1–5 |
| `timestamp` | TEXT | ISO 8601 |

> **Schema migration**: if the table was created with the old schema (which had `guessed_ai_index`/`scenario_id`), `init_db()` automatically drops and recreates it with the new schema. This is safe to run before the event; after real data exists the `item_id` column will already be present so the migration is skipped.

### `turing_tasks`
Multi-select trust tasks; one row per task per respondent.

| Column | Type | Notes |
|---|---|---|
| `respondent_id` | TEXT | FK to `turing_responses` |
| `task` | TEXT | Selected from `TRUST_TASKS` |

### `acceptance_responses`
One row per AI Acceptance Survey respondent.

| Column | Type | Notes |
|---|---|---|
| `participant_id` | TEXT | Short UUID (8 chars) |
| `timestamp` | TEXT | ISO 8601 |
| `age_group` | TEXT | Part A Q1 |
| `gender` | TEXT | Part A Q2 |
| `cluster` | TEXT | Part A Q3 — plain text; `"Others; <text>"` for free-text entry |
| `disciplines` | TEXT | Part A Q4 — single-element JSON array e.g. `["Medicine"]` or `["Other; Data Scientist"]` |
| `years_healthcare` | TEXT | Part A Q6 |
| `years_role` | TEXT | Part A Q7 |
| `seniority` | TEXT | Part A Q5 — full tier label e.g. `"Student (Medical Student)"`, derived from discipline at render time |
| `ai_frequency` | TEXT | Part A Q8 |
| `ai_tools` | TEXT | Part A Q9 — JSON array of selected tool categories (multi-select) |
| `likert_answers` | TEXT | JSON object e.g. `{"B1": 3, "B2": 4, ..., "D7": 5}` covering all 22 questions across Parts B–D |
| `open_reflection` | TEXT | JSON object e.g. `{"G1": "...", "G2": "...", "G3": "...", "G4": "..."}` — Part G optional free-text responses |

> The `is_ai` and `correct_answer` fields in `TURING_ITEMS` are **never stored in the DB**. They are embedded in the survey page JS for client-side inline reveal only (acceptable for a booth activity with no security requirement).

---

## API Reference

### Submit a sentiment response

```
POST /api/submit
Content-Type: application/json

{
  "text": "I think AI could help with documentation...",
  "question_index": 0,
  "participant_id": "abc12345"   // optional
}
```

Response:
```json
{
  "entry": {
    "text": "...",
    "sentiment": { "polarity": 0.3, "subjectivity": 0.6, "label": "Positive", "emoji": "😊", "color": "#22c55e" },
    "timestamp": "2026-03-25T10:00:00"
  }
}
```

> Note: `polarity` is stored and returned in the API response but is **not displayed** to participants in the survey UI — only the sentiment label is shown.

Error response (profanity detected):
```json
HTTP 400
{ "error": "Inappropriate content" }
```

### Submit an AI vs Human survey

```
POST /api/turing/submit
Content-Type: application/json

{
  "job_group": "Nurse",
  "seniority": "Mid-career (5–15 years)",
  "answers": [
    {
      "item_id": "scenario_1",
      "section": "Scenario",
      "guess": "Human Clinician",
      "ratings": { "trust": 4, "empathy": 5, "safety": 4, "usefulness": 3 }
    },
    {
      "item_id": "conversation_1",
      "section": "Conversation",
      "guess": "AI",
      "ratings": { "trust": 3, "empathy": 2, "safety": 3, "usefulness": 3 }
    }
  ],
  "tasks": ["Triaging symptoms", "Patient education"]
}
```

Response includes `results[]` with `item_id`, `correct` (bool), and `correct_answer` per item.

> `job_group` may be `"Other; Facilities Management"` when the participant selected "Other" and typed a custom role.

### Submit an AI Acceptance Survey

```
POST /api/acceptance/submit
Content-Type: application/json

{
  "part_a": {
    "age_group": "30–39",
    "gender": "Female",
    "cluster": "National University Health System",
    "disciplines": ["Medicine"],
    "seniority": "Senior (Resident Physician, Associate Consultant, Consultant, Senior Consultant)",
    "years_healthcare": "6–10 years",
    "years_role": "4–7 years",
    "ai_frequency": "Sometimes",
    "ai_tools": ["Commercial AI (ChatGPT, Gemini, Claude)"]
  },
  "likert_answers": {
    "B1": 4, "B2": 3, "B3": 5, "B4": 4, "B5": 3, "B6": 4, "B7": 5,
    "C1": 2, "C2": 3, "C3": 2, "C4": 3, "C5": 2, "C6": 5, "C7": 4, "C8": 4,
    "D1": 3, "D2": 4, "D3": 3, "D4": 3, "D5": 4, "D6": 4, "D7": 5
  },
  "open_reflection": {
    "G1": "I'd like AI to help with documentation and note-taking.",
    "G2": "I worry about over-reliance reducing clinical judgement.",
    "G3": "Better training and clear evidence of benefit.",
    "G4": ""
  }
}
```

---

## Exporting Data

### JSON export

```
GET /api/export
```

Returns a single JSON object containing all sentiment responses (keyed by question text), full Turing test stats, and acceptance survey stats.

### Excel export

```
GET /api/export/excel
```

Downloads a `.xlsx` file (`nuhs_summit_YYYYMMDD_HHMM.xlsx`) with three sheets:

| Sheet | Format | Contents |
|---|---|---|
| **Sentiment Responses** | Wide (one row per participant) | Participant ID + Q1–Q4 transcript, sentiment label, polarity + timestamp |
| **Turing Test** | Wide (one row per respondent) | Participant ID, job group, seniority, trusted tasks + per-item correct/ratings (Scenario 1–3 then Conversation 1–2, 5 columns each) |
| **AI Acceptance Survey** | Wide (one row per respondent) | All Part A fields (incl. Cluster) + one column per Likert question (full question text as header, Parts B–D) + four Part G open-reflection columns |

---

## Design System

All templates use a Google Material Design-inspired light theme. Do not introduce dark backgrounds or light-on-dark text.

| Token | Value | Usage |
|---|---|---|
| Background | `#ffffff` / `#f1f3f4` | Page and card backgrounds |
| Primary text | `#202124` | Headings and body |
| Secondary text | `#5f6368` | Subtitles and hints |
| Tertiary text | `#80868b` | Credits, timestamps |
| Border | `#dadce0` | Card outlines, dividers |
| Indigo accent | `#4f46e5` / `#6366f1` | Primary buttons, active states |
| Purple accent | `#a855f7` / `#9333ea` | AI Acceptance highlights; admin `--pu` |
| Pink accent | `#ec4899` / `#db2777` | AI vs Human highlights; admin `--pk` |
| Cyan accent | `#06b6d4` | AI Perspectives highlights; admin `--cy` |
| Amber accent | `#f59e0b` | Live Overview tab; admin `--am` |

**Logo**: `HCRD.png` from `/static/`. Size is controlled via inline `height` on the `<img>` tag in each template — do not modify the image file itself.
