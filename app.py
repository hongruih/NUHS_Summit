"""
=============================================================================
  REAL-TIME SENTIMENT ANALYSIS & WORD CLOUD BOOTH TOOL  
  For NUH AI Summit — Interactive Audience Engagement
=============================================================================


    ✓ AI vs Human Turing Test module — clinical scenarios with two answers
    ✓ Respondents guess which answer is AI vs Human, then rate trust/empathy/safety/usefulness
    ✓ Demographic capture: job group + seniority level
    ✓ Dashboard analytics: % correct by job group/seniority (tests Dr Alex's hypothesis)
    ✓ QR-code accessible standalone survey page (/survey)
    ✓ Results flash on the main dashboard in real-time
    ✓ SQLite persistence (survives restarts)
    ✓ All previous features preserved (live transcription, word clouds, sentiment)

  Layout:
    Tab 1: LIVE OVERVIEW       — Aggregate word cloud + sentiment + Turing snapshot
    Tab 2: Q1 Input            — Record/type + per-question dashboard
    Tab 3: Q2 Input            — Record/type + per-question dashboard
    Tab 4: Q3 Input            — Record/type + per-question dashboard
    Tab 5: PER-Q DASHBOARD     — All 3 questions word clouds + sentiments
    Tab 6: AI vs HUMAN         — Turing test survey + results dashboard

  Standalone:
    /survey                    — Mobile-friendly QR survey (walk-away)
    /qr                        — QR code image for /survey

  Requirements:
      pip install flask textblob qrcode pillow

  Usage:
      python app.py  →  open http://localhost:5001

  Author: Ravi 
=============================================================================
"""

import os, io, re, base64, json, sqlite3, uuid
from collections import Counter
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify, send_file, Response
from textblob import TextBlob

APP_TITLE = "AI Perspectives — Live Sentiment Booth"
QUESTIONS = [
    "What changes, if any, do you anticipate AI bringing to your work?",
    "What would make you more confident or willing to use AI tools in your daily practice?",
    "Is there anything else you would like to share about AI in healthcare?",
]
STOP_WORDS = set("i me my myself we our ours ourselves you your yours yourself yourselves "
    "he him his himself she her hers herself it its itself they them their theirs "
    "themselves what which who whom this that these those am is are was were be been "
    "being have has had having do does did doing a an the and but if or because as "
    "until while of at by for with about against between through during before after "
    "above below to from up down in out on off over under again further then once "
    "here there when where why how all both each few more most other some such no nor "
    "not only own same so than too very s t can will just don should now d ll m o re "
    "ve y ain aren couldn didn doesn hadn hasn haven isn ma mightn mustn needn shan "
    "shouldn wasn weren won wouldn think also like really would could one thing things "
    "going know actually mean yeah yes well okay sure right get got say said something "
    "lot much many still even want need gonna make way feel see look come kind sort "
    "maybe might quite already".split())

# ═══════════════════════════════════════════════════════
# CLINICAL SCENARIOS — AI vs HUMAN TURING TEST
# Each scenario: patient complaint + two responses (one AI, one human doctor)
# "ai_index" = which response (0 or 1) is the AI-generated one
# ═══════════════════════════════════════════════════════
SCENARIOS = [
    {
        "id": "s1",
        "patient": "I've tried to lose weight many times, but I always gain it back. I feel like I'm failing, and maybe this is just who I am. What should I do?",
        "responses": [
            "It sounds like you've been through a lot. Weight management is complex — it's not just willpower. I'd recommend seeing your doctor to discuss metabolic factors, possible hormonal issues, and evidence-based approaches like structured programmes. You're not failing; you're dealing with something that often requires professional support.",
            "That's okay! Weight fluctuates naturally and many people go through this. Try to focus on being happy and not stress about the number on the scale. Maybe try some gentle exercise when you feel like it, and things should balance out on their own over time."
        ],
        "ai_index": 1,
        "explanation": "The AI response (Response B) offers generic reassurance without recommending medical evaluation. A doctor would investigate underlying metabolic or hormonal causes and recommend evidence-based interventions."
    },
    {
        "id": "s2",
        "patient": "I feel a tightness in my chest when I walk upstairs. It goes away when I rest. Should I just monitor it at home?",
        "responses": [
            "Since the discomfort goes away when you rest, it's likely just from exertion. You can monitor it for now — try taking the stairs more slowly and stay hydrated. If it gets worse over the next few weeks, consider seeing a doctor.",
            "Please don't wait on this. Chest tightness triggered by exertion that resolves with rest is a classic pattern for angina, which can signal coronary artery disease. You should see a doctor as soon as possible for an ECG and further cardiac workup. This is not something to monitor at home."
        ],
        "ai_index": 0,
        "explanation": "The AI response (Response A) dangerously normalises exertional chest tightness. A physician would recognise this as a red-flag pattern for angina pectoris requiring urgent cardiac investigation."
    },
    {
        "id": "s3",
        "patient": "My child has had a fever of 38.5°C for two days and a rash appeared this morning. She's still eating and playing. Can I just give paracetamol and wait?",
        "responses": [
            "A persistent fever with a new rash warrants a same-day medical review, even if your child seems well. Rashes with fever can indicate a range of conditions — some benign, some serious — that need a clinical assessment to differentiate. Please bring her to your paediatrician or A&E today.",
            "A 38.5°C fever is considered mild, and since she's still active and eating, those are good signs. You can continue paracetamol as directed and keep her comfortable. The rash is likely viral and should clear in a few days. Just watch for any changes in behaviour."
        ],
        "ai_index": 1,
        "explanation": "The AI response (Response B) reassures without examination. A doctor would insist on same-day review because fever + new rash requires clinical differentiation to rule out serious conditions like meningococcaemia or Kawasaki disease."
    },
    {
        "id": "s4",
        "patient": "I've been feeling really down for the past few months. I don't enjoy things I used to, and I'm sleeping a lot more. Is this just a phase?",
        "responses": [
            "It's normal to have ups and downs in life. Try to get some fresh air, exercise regularly, and connect with friends. Keeping a gratitude journal can also help shift your perspective. If it continues for a few more months, you might want to talk to someone.",
            "What you're describing — persistent low mood, loss of interest, and changes in sleep for months — are core symptoms of major depressive disorder. I'd strongly encourage you to see your GP or a mental health professional soon. Depression is treatable, and early intervention leads to better outcomes. This is not something you should wait out."
        ],
        "ai_index": 0,
        "explanation": "The AI response (Response A) offers lifestyle platitudes and suggests waiting months longer. A clinician would recognise DSM-5 criteria for major depression and recommend prompt professional evaluation."
    },
    {
        "id": "s5",
        "patient": "I accidentally took double my blood pressure medication this morning. I feel okay so far. Should I be worried?",
        "responses": [
            "An accidental double dose of antihypertensive medication can cause a significant drop in blood pressure, potentially leading to dizziness, fainting, or falls — even if you feel fine right now. Please call your doctor or pharmacist immediately, monitor for symptoms like lightheadedness, and do not take your next scheduled dose without medical advice.",
            "Don't worry too much — taking a double dose once is unlikely to cause serious harm. Just skip your next dose to balance it out, drink plenty of water, and rest today. Your body can handle the extra medication this one time."
        ],
        "ai_index": 1,
        "explanation": "The AI response (Response B) trivialises a medication error. Advising to simply 'skip the next dose' without professional guidance is dangerous — a physician would recommend immediate contact with a healthcare provider for monitoring and dose adjustment."
    }
]

JOB_GROUPS = ["Junior Doctor / HO / MO", "Senior Doctor / Consultant", "Nurse", "Allied Health Professional",
              "Clinical Research Coordinator / Scientist", "Administrator / Management", "Student", "Other"]
SENIORITY_LEVELS = ["Junior (< 5 years experience)", "Mid-career (5–15 years)", "Senior (> 15 years)"]
TRUST_TASKS = ["Triaging symptoms", "Drafting clinical notes", "Patient education",
               "Medication counselling", "Mental health screening", "Diagnostic support"]

# ═══════════════════════════════════════════════════════
# DATABASE SETUP
# ═══════════════════════════════════════════════════════
DB_PATH = "booth_data.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    # Sentiment responses (migrated from in-memory store)
    c.execute("""CREATE TABLE IF NOT EXISTS sentiment_responses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question_index INTEGER NOT NULL,
        text TEXT NOT NULL,
        polarity REAL,
        subjectivity REAL,
        label TEXT,
        emoji TEXT,
        color TEXT,
        timestamp TEXT
    )""")
    # Turing test responses
    c.execute("""CREATE TABLE IF NOT EXISTS turing_responses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        respondent_id TEXT NOT NULL,
        job_group TEXT,
        seniority TEXT,
        timestamp TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS turing_answers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        respondent_id TEXT NOT NULL,
        scenario_id TEXT NOT NULL,
        guessed_ai_index INTEGER NOT NULL,
        correct INTEGER NOT NULL,
        rating_trust INTEGER,
        rating_empathy INTEGER,
        rating_safety INTEGER,
        rating_usefulness INTEGER,
        timestamp TEXT
    )""")
    # AI trust tasks
    c.execute("""CREATE TABLE IF NOT EXISTS turing_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        respondent_id TEXT NOT NULL,
        task TEXT NOT NULL
    )""")
    conn.commit()
    conn.close()

init_db()

app = Flask(__name__)

# ═══════════════════════════════════════════════════════
# SENTIMENT HELPERS (unchanged logic, now with SQLite)
# ═══════════════════════════════════════════════════════
def sentiment(text):
    b = TextBlob(text)
    p = b.sentiment.polarity
    s = b.sentiment.subjectivity
    if p > 0.15:
        return {"polarity": round(p, 3), "subjectivity": round(s, 3),
                "label": "Positive", "emoji": "😊", "color": "#22c55e"}
    elif p < -0.15:
        return {"polarity": round(p, 3), "subjectivity": round(s, 3),
                "label": "Negative", "emoji": "😟", "color": "#ef4444"}
    else:
        return {"polarity": round(p, 3), "subjectivity": round(s, 3),
                "label": "Neutral", "emoji": "😐", "color": "#f59e0b"}

def extract_words(texts):
    combined = re.sub(r"[^a-zA-Z\s]", "", " ".join(texts).lower())
    words = [w for w in combined.split() if w not in STOP_WORDS and len(w) > 2]
    freq = Counter(words)
    return [{"text": w, "value": c} for w, c in freq.most_common(80)]

def get_entries(q):
    conn = get_db()
    rows = conn.execute("SELECT * FROM sentiment_responses WHERE question_index=? ORDER BY id", (q,)).fetchall()
    conn.close()
    return [{"text": r["text"], "sentiment": {"polarity": r["polarity"], "subjectivity": r["subjectivity"],
             "label": r["label"], "emoji": r["emoji"], "color": r["color"]}, "timestamp": r["timestamp"]} for r in rows]

def stats_for(entries):
    if not entries:
        return {"positive": 0, "negative": 0, "neutral": 0, "avg_polarity": 0, "total": 0}
    p = sum(1 for e in entries if e["sentiment"]["label"] == "Positive")
    n = sum(1 for e in entries if e["sentiment"]["label"] == "Negative")
    u = sum(1 for e in entries if e["sentiment"]["label"] == "Neutral")
    a = sum(e["sentiment"]["polarity"] for e in entries) / len(entries)
    return {"positive": p, "negative": n, "neutral": u, "avg_polarity": round(a, 3), "total": len(entries)}


# ═══════════════════════════════════════════════════════
# TURING TEST ANALYTICS
# ═══════════════════════════════════════════════════════
def get_turing_stats():
    conn = get_db()
    total_respondents = conn.execute("SELECT COUNT(*) as c FROM turing_responses").fetchone()["c"]
    if total_respondents == 0:
        conn.close()
        return {"total_respondents": 0, "overall_accuracy": 0, "by_job_group": {}, "by_seniority": {},
                "by_scenario": {}, "avg_ratings": {}, "trust_tasks": {}, "respondents_list": []}

    # Overall accuracy
    total_answers = conn.execute("SELECT COUNT(*) as c FROM turing_answers").fetchone()["c"]
    total_correct = conn.execute("SELECT COUNT(*) as c FROM turing_answers WHERE correct=1").fetchone()["c"]
    overall_accuracy = round(total_correct / total_answers * 100, 1) if total_answers else 0

    # By job group
    by_job = {}
    for jg in JOB_GROUPS:
        rows = conn.execute("""
            SELECT COUNT(a.id) as total, SUM(a.correct) as correct_sum
            FROM turing_answers a JOIN turing_responses r ON a.respondent_id=r.respondent_id
            WHERE r.job_group=?""", (jg,)).fetchone()
        t, c = rows["total"] or 0, rows["correct_sum"] or 0
        if t > 0:
            by_job[jg] = {"total": t, "correct": c, "accuracy": round(c / t * 100, 1),
                          "fooled_pct": round((t - c) / t * 100, 1)}

    # By seniority
    by_sen = {}
    for sl in SENIORITY_LEVELS:
        rows = conn.execute("""
            SELECT COUNT(a.id) as total, SUM(a.correct) as correct_sum
            FROM turing_answers a JOIN turing_responses r ON a.respondent_id=r.respondent_id
            WHERE r.seniority=?""", (sl,)).fetchone()
        t, c = rows["total"] or 0, rows["correct_sum"] or 0
        if t > 0:
            by_sen[sl] = {"total": t, "correct": c, "accuracy": round(c / t * 100, 1),
                          "fooled_pct": round((t - c) / t * 100, 1)}

    # By scenario
    by_sc = {}
    for sc in SCENARIOS:
        rows = conn.execute("SELECT COUNT(*) as total, SUM(correct) as correct_sum FROM turing_answers WHERE scenario_id=?",
                            (sc["id"],)).fetchone()
        t, c = rows["total"] or 0, rows["correct_sum"] or 0
        if t > 0:
            by_sc[sc["id"]] = {"total": t, "correct": c, "accuracy": round(c / t * 100, 1)}

    # Average ratings
    rat = conn.execute("""SELECT AVG(rating_trust) as t, AVG(rating_empathy) as e,
                          AVG(rating_safety) as s, AVG(rating_usefulness) as u FROM turing_answers""").fetchone()
    avg_ratings = {"trust": round(rat["t"] or 0, 2), "empathy": round(rat["e"] or 0, 2),
                   "safety": round(rat["s"] or 0, 2), "usefulness": round(rat["u"] or 0, 2)}

    # Trust tasks
    task_rows = conn.execute("SELECT task, COUNT(*) as c FROM turing_tasks GROUP BY task ORDER BY c DESC").fetchall()
    trust_tasks = {r["task"]: r["c"] for r in task_rows}

    # Recent respondents
    recent = conn.execute("SELECT * FROM turing_responses ORDER BY id DESC LIMIT 20").fetchall()
    respondents_list = [{"respondent_id": r["respondent_id"], "job_group": r["job_group"],
                         "seniority": r["seniority"], "timestamp": r["timestamp"]} for r in recent]

    conn.close()
    return {
        "total_respondents": total_respondents,
        "overall_accuracy": overall_accuracy,
        "total_answers": total_answers,
        "total_correct": total_correct,
        "by_job_group": by_job,
        "by_seniority": by_sen,
        "by_scenario": by_sc,
        "avg_ratings": avg_ratings,
        "trust_tasks": trust_tasks,
        "respondents_list": respondents_list
    }


# ═══════════════════════════════════════════════════════
# ROUTES — EXISTING (sentiment)
# ═══════════════════════════════════════════════════════
@app.route("/")
def index():
    return render_template_string(TMPL, questions=QUESTIONS, title=APP_TITLE,
                                  stop_words=sorted(STOP_WORDS),
                                  scenarios=SCENARIOS, job_groups=JOB_GROUPS,
                                  seniority_levels=SENIORITY_LEVELS,
                                  trust_tasks=TRUST_TASKS)


@app.route("/api/submit", methods=["POST"])
def api_submit():
    d = request.json
    t = (d.get("text") or "").strip()
    q = d.get("question_index", 0)
    if not t:
        return jsonify({"error": "Empty"}), 400
    s = sentiment(t)
    conn = get_db()
    conn.execute("INSERT INTO sentiment_responses (question_index,text,polarity,subjectivity,label,emoji,color,timestamp) VALUES (?,?,?,?,?,?,?,?)",
                 (q, t, s["polarity"], s["subjectivity"], s["label"], s["emoji"], s["color"], datetime.now().isoformat()))
    conn.commit()
    conn.close()
    entry = {"text": t, "sentiment": s, "timestamp": datetime.now().isoformat()}
    return jsonify({"entry": entry})


@app.route("/api/q/<int:q>")
def api_q(q):
    entries = get_entries(q)
    texts = [e["text"] for e in entries]
    return jsonify({
        "words": extract_words(texts) if texts else [],
        "stats": stats_for(entries),
        "entries": entries[-15:]
    })


@app.route("/api/all")
def api_all():
    r = {}
    for i in range(3):
        entries = get_entries(i)
        texts = [e["text"] for e in entries]
        r[str(i)] = {"words": extract_words(texts) if texts else [],
                      "stats": stats_for(entries), "entries": entries[-10:]}
    ae = []
    for i in range(3):
        ae.extend(get_entries(i))
    at = [e["text"] for e in ae]
    r["agg"] = {"words": extract_words(at) if at else [], "stats": stats_for(ae)}
    # Include turing snapshot
    r["turing"] = get_turing_stats()
    return jsonify(r)


@app.route("/api/reset", methods=["POST"])
def api_reset():
    conn = get_db()
    conn.execute("DELETE FROM sentiment_responses")
    conn.execute("DELETE FROM turing_responses")
    conn.execute("DELETE FROM turing_answers")
    conn.execute("DELETE FROM turing_tasks")
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/export")
def api_export():
    data = {}
    for i in range(3):
        data[QUESTIONS[i]] = get_entries(i)
    data["turing_test"] = get_turing_stats()
    return jsonify(data)


# ═══════════════════════════════════════════════════════
# ROUTES — TURING TEST
# ═══════════════════════════════════════════════════════
@app.route("/api/turing/submit", methods=["POST"])
def api_turing_submit():
    d = request.json
    rid = d.get("respondent_id") or str(uuid.uuid4())[:8]
    job_group = d.get("job_group", "")
    seniority = d.get("seniority", "")
    answers = d.get("answers", [])  # [{scenario_id, guessed_ai_index, ratings:{trust,empathy,safety,usefulness}}]
    tasks = d.get("tasks", [])  # list of task strings

    if not answers:
        return jsonify({"error": "No answers"}), 400

    conn = get_db()
    ts = datetime.now().isoformat()
    conn.execute("INSERT INTO turing_responses (respondent_id,job_group,seniority,timestamp) VALUES (?,?,?,?)",
                 (rid, job_group, seniority, ts))

    for a in answers:
        sid = a.get("scenario_id", "")
        guessed = a.get("guessed_ai_index", -1)
        # Find correct answer
        sc = next((s for s in SCENARIOS if s["id"] == sid), None)
        correct = 1 if (sc and guessed == sc["ai_index"]) else 0
        ratings = a.get("ratings", {})
        conn.execute("""INSERT INTO turing_answers
            (respondent_id,scenario_id,guessed_ai_index,correct,rating_trust,rating_empathy,rating_safety,rating_usefulness,timestamp)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (rid, sid, guessed, correct,
             ratings.get("trust", 0), ratings.get("empathy", 0),
             ratings.get("safety", 0), ratings.get("usefulness", 0), ts))

    for task in tasks:
        conn.execute("INSERT INTO turing_tasks (respondent_id,task) VALUES (?,?)", (rid, task))

    conn.commit()
    conn.close()

    # Return result
    results = []
    for a in answers:
        sc = next((s for s in SCENARIOS if s["id"] == a.get("scenario_id")), None)
        if sc:
            results.append({
                "scenario_id": sc["id"],
                "correct": a.get("guessed_ai_index") == sc["ai_index"],
                "ai_index": sc["ai_index"],
                "explanation": sc["explanation"]
            })

    return jsonify({"ok": True, "respondent_id": rid, "results": results})


@app.route("/api/turing/stats")
def api_turing_stats():
    return jsonify(get_turing_stats())


@app.route("/api/turing/scenarios")
def api_turing_scenarios():
    """Return scenarios without revealing which is AI (for the survey form)."""
    safe = []
    for s in SCENARIOS:
        safe.append({"id": s["id"], "patient": s["patient"], "responses": s["responses"]})
    return jsonify({"scenarios": safe, "job_groups": JOB_GROUPS,
                    "seniority_levels": SENIORITY_LEVELS, "trust_tasks": TRUST_TASKS})


# ═══════════════════════════════════════════════════════
# QR CODE & STANDALONE SURVEY
# ═══════════════════════════════════════════════════════
@app.route("/survey")
def survey_page():
    return render_template_string(SURVEY_TMPL, title=APP_TITLE,
                                  scenarios_json=json.dumps([{"id": s["id"], "patient": s["patient"],
                                  "responses": s["responses"]} for s in SCENARIOS]),
                                  job_groups=JOB_GROUPS, seniority_levels=SENIORITY_LEVELS,
                                  trust_tasks=TRUST_TASKS)


@app.route("/qr")
def qr_code():
    import qrcode
    host = request.host_url.rstrip("/")
    url = f"{host}/survey"
    img = qrcode.make(url, box_size=10, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png", download_name="survey_qr.png")


# ═══════════════════════════════════════════════════════
# MAIN TEMPLATE (enhanced with Turing test tab)
# ═══════════════════════════════════════════════════════
TMPL = r"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ title }}</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3-cloud/1.2.7/d3.layout.cloud.min.js"></script>
<style>
:root{--bg:#0a0e1a;--c1:#111827;--c2:#1a2235;--bd:#1e293b;--t1:#f1f5f9;--t2:#94a3b8;--t3:#64748b;
--bl:#3b82f6;--cy:#06b6d4;--gn:#22c55e;--rd:#ef4444;--am:#f59e0b;--pu:#a855f7;--pk:#ec4899;--r:12px;--rs:8px}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'DM Sans',sans-serif;background:var(--bg);color:var(--t1);min-height:100vh}

.hdr{padding:14px 28px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid var(--bd);background:rgba(10,14,26,.95);backdrop-filter:blur(20px);position:sticky;top:0;z-index:100}
.hdr h1{font-size:1.15rem;font-weight:700;background:linear-gradient(135deg,var(--bl),var(--cy));-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.pills{display:flex;gap:8px;align-items:center}
.pill{font-family:'Space Mono',monospace;font-size:.68rem;padding:3px 10px;border-radius:20px;background:var(--c1);border:1px solid var(--bd);color:var(--t2)}
.pill.on{border-color:var(--gn);color:var(--gn);animation:pls 2s infinite}
@keyframes pls{0%,100%{box-shadow:0 0 0 0 rgba(34,197,94,.3)}50%{box-shadow:0 0 0 4px rgba(34,197,94,.1)}}

.tabs{display:flex;border-bottom:1px solid var(--bd);background:var(--c1);overflow-x:auto}
.tab{font-family:'DM Sans',sans-serif;font-size:.78rem;font-weight:500;padding:11px 20px;border:none;background:0;color:var(--t3);cursor:pointer;border-bottom:2px solid transparent;white-space:nowrap;transition:.2s}
.tab:hover{color:var(--t1);background:var(--c2)}.tab.on{color:var(--cy);border-bottom-color:var(--cy)}
.tab.ov{color:var(--am)}.tab.ov.on{color:var(--am);border-bottom-color:var(--am)}
.tab.tt{color:var(--pk)}.tab.tt.on{color:var(--pk);border-bottom-color:var(--pk)}
.tab.dt{margin-left:auto}

.pnl{display:none}.pnl.on{display:block}

/* ═══ OVERVIEW ═══ */
.ov-wrap{padding:24px 28px;max-width:1100px;margin:0 auto}
.ov-title{font-size:1rem;font-weight:600;margin-bottom:16px;color:var(--t2)}.ov-title b{color:var(--am)}
.ov-grid{display:grid;grid-template-columns:1fr;gap:20px;margin-bottom:20px}
.ov-wc-row{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
.ov-wc-card{border-radius:var(--r);border:1px solid var(--bd);background:var(--c1);padding:14px;display:flex;flex-direction:column}
.ov-wc-card.q0{border-color:rgba(6,182,212,.2)}.ov-wc-card.q1{border-color:rgba(168,85,247,.2)}.ov-wc-card.q2{border-color:rgba(245,158,11,.2)}
.ov-wc-card h3{font-size:.62rem}.ov-wc-card .qtext{font-size:.72rem;color:var(--t2);line-height:1.4;margin-bottom:8px}
.ov-card{border-radius:var(--r);border:1px solid var(--bd);background:var(--c1);padding:18px;display:flex;flex-direction:column}
.ov-card h3,.card h3{font-size:.7rem;font-family:'Space Mono',monospace;text-transform:uppercase;letter-spacing:.08em;color:var(--t3);margin-bottom:10px}
.ov-wc{flex:1;display:flex;align-items:center;justify-content:center;min-height:220px}
.ov-empty{color:var(--t3);text-align:center;padding:50px 20px;font-size:.88rem}
.big3{display:flex;gap:10px}
.b3{flex:1;text-align:center;padding:14px 8px;border-radius:var(--rs);background:var(--c2)}
.b3 .n{font-size:1.8rem;font-weight:700;display:block}.b3 .l{font-size:.6rem;font-family:'Space Mono',monospace;color:var(--t3)}
.b3.gn .n{color:var(--gn)}.b3.am .n{color:var(--am)}.b3.rd .n{color:var(--rd)}.b3.pk .n{color:var(--pk)}.b3.cy .n{color:var(--cy)}.b3.bl .n{color:var(--bl)}
.avg{font-family:'Space Mono',monospace;font-size:.72rem;color:var(--t3);text-align:center;margin-top:8px}
.pqg{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:10px}
.pqb{border-radius:var(--rs);border:1px solid var(--bd);background:var(--c1);padding:12px}
.pqb h4{font-size:.62rem;font-family:'Space Mono',monospace;text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px}
.pqb.q0 h4{color:var(--cy)}.pqb.q1 h4{color:var(--pu)}.pqb.q2 h4{color:var(--am)}
.pqn{display:flex;gap:6px;font-size:.72rem;font-weight:600}
.pqn span{flex:1;text-align:center;padding:4px;border-radius:4px;background:var(--c2)}
.pqn .g{color:var(--gn)}.pqn .a{color:var(--am)}.pqn .r{color:var(--rd)}
.pqt{font-size:.62rem;color:var(--t3);font-family:'Space Mono',monospace;margin-top:4px}

/* ═══ TURING SNAPSHOT (overview page) ═══ */
.ts-card{border-radius:var(--r);border:1px solid rgba(236,72,153,.2);background:linear-gradient(135deg,rgba(236,72,153,.04),rgba(168,85,247,.04));padding:18px;margin-top:10px}
.ts-card h3{color:var(--pk)}
.ts-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:8px}
.ts-stat{text-align:center;padding:10px 4px;border-radius:var(--rs);background:var(--c2)}
.ts-stat .n{font-size:1.4rem;font-weight:700;display:block;color:var(--pk)}
.ts-stat .l{font-size:.58rem;font-family:'Space Mono',monospace;color:var(--t3)}

/* ═══ INPUT PANELS ═══ */
.ip{display:grid;grid-template-columns:.7fr 1.3fr;min-height:calc(100vh - 110px)}
.ip-l{padding:18px 22px;border-right:1px solid var(--bd);display:flex;flex-direction:column;gap:12px}
.ip-r{padding:22px 28px;overflow-y:auto;display:flex;flex-direction:column;gap:16px}
.qban{font-size:1rem;font-weight:500;line-height:1.5;padding:14px 16px;border-radius:var(--r);border:1px solid rgba(59,130,246,.15)}
.qban.q0{background:linear-gradient(135deg,rgba(59,130,246,.07),rgba(6,182,212,.07))}
.qban.q1{background:linear-gradient(135deg,rgba(168,85,247,.07),rgba(236,72,153,.07));border-color:rgba(168,85,247,.15)}
.qban.q2{background:linear-gradient(135deg,rgba(245,158,11,.07),rgba(239,68,68,.07));border-color:rgba(245,158,11,.15)}
.qban .qn{font-family:'Space Mono',monospace;font-size:.58rem;text-transform:uppercase;letter-spacing:.1em;display:block;margin-bottom:5px}
.qban.q0 .qn{color:var(--cy)}.qban.q1 .qn{color:var(--pu)}.qban.q2 .qn{color:var(--am)}

.ma{display:flex;flex-direction:column;align-items:center;gap:10px;padding:12px 0}
.mb{width:72px;height:72px;border-radius:50%;border:3px solid var(--bd);background:var(--c1);cursor:pointer;display:flex;align-items:center;justify-content:center;transition:.3s}
.mb:hover{border-color:var(--bl);transform:scale(1.05)}
.mb.rec{border-color:var(--rd);background:rgba(239,68,68,.1);animation:mp 1.5s infinite}
@keyframes mp{0%,100%{box-shadow:0 0 0 0 rgba(239,68,68,.4)}50%{box-shadow:0 0 0 12px rgba(239,68,68,0)}}
.mb svg{width:28px;height:28px;fill:var(--t1)}.mb.rec svg{fill:var(--rd)}
.ml{font-size:.72rem;color:var(--t3);font-family:'Space Mono',monospace}
.ml.live{color:var(--gn)}

.tx{min-height:60px;max-height:120px;padding:10px;border-radius:var(--r);border:1px solid var(--bd);background:var(--c1);font-size:.84rem;line-height:1.5;color:var(--t1);resize:none;font-family:'DM Sans',sans-serif;outline:none;flex:0 0 auto}
.tx:focus{border-color:var(--bl)}.tx::placeholder{color:var(--t3)}
.tx.listening{border-color:var(--gn);box-shadow:0 0 0 2px rgba(34,197,94,.15)}
.br{display:flex;gap:8px}
.btn{font-family:'DM Sans',sans-serif;font-size:.8rem;font-weight:600;padding:9px 18px;border-radius:var(--rs);border:none;cursor:pointer;transition:.2s}
.bp{background:linear-gradient(135deg,var(--bl),var(--cy));color:#fff}.bp:hover{opacity:.9}.bp:disabled{opacity:.4;cursor:not-allowed}
.bg{background:0;border:1px solid var(--bd);color:var(--t2)}.bg:hover{background:var(--c2)}
.bpk{background:linear-gradient(135deg,var(--pk),var(--pu));color:#fff}.bpk:hover{opacity:.9}

.lr{padding:12px;border-radius:var(--r);border:1px solid var(--bd);background:var(--c1);display:none}
.lr.vis{display:block;animation:fi .3s}
.lr-top{display:flex;align-items:center;gap:8px;margin-bottom:6px}
.lr-em{font-size:1.4rem}.lr-lb{font-weight:700;font-size:.9rem}.lr-pl{font-family:'Space Mono',monospace;font-size:.65rem;color:var(--t3)}
.lr-bar{height:4px;border-radius:2px;background:var(--bd);overflow:hidden;margin-top:4px}
.lr-fill{height:100%;border-radius:2px;transition:width .5s}

.card{border-radius:var(--r);border:1px solid var(--bd);background:var(--c1);padding:16px}
.wci{width:100%;min-height:260px;display:flex;align-items:center;justify-content:center}
.wci svg{width:100%;height:auto}
.sbs{display:flex;gap:8px;align-items:flex-end;height:120px}
.sbc{flex:1;display:flex;flex-direction:column;align-items:center;gap:3px}
.sbt{width:100%;height:90px;background:var(--bd);border-radius:5px;overflow:hidden;display:flex;align-items:flex-end}
.sbf{width:100%;border-radius:5px;transition:height .6s}
.sbl{font-size:.58rem;font-family:'Space Mono',monospace;color:var(--t3)}
.sbn{font-size:.78rem;font-weight:700}
.fd{display:flex;flex-direction:column;gap:5px;max-height:300px;overflow-y:auto}
.fdi{padding:7px 10px;border-radius:var(--rs);background:var(--c2);border-left:3px solid var(--bd);font-size:.74rem;line-height:1.4;color:var(--t2);animation:si .3s}
.fdi .fs{font-family:'Space Mono',monospace;font-size:.58rem;margin-top:2px;display:block}
.emp{color:var(--t3);font-size:.8rem;text-align:center;padding:30px}

/* ═══ FULL DASHBOARD ═══ */
.dg{display:grid;gap:20px;padding:24px 28px;max-width:1100px;margin:0 auto}
.dblk{border-radius:var(--r);border:1px solid var(--bd);background:var(--c1);overflow:hidden}
.dhd{padding:12px 18px;font-size:.88rem;font-weight:500;line-height:1.4;border-bottom:1px solid var(--bd)}
.dhd.q0{background:linear-gradient(135deg,rgba(59,130,246,.05),rgba(6,182,212,.05))}
.dhd.q1{background:linear-gradient(135deg,rgba(168,85,247,.05),rgba(236,72,153,.05))}
.dhd.q2{background:linear-gradient(135deg,rgba(245,158,11,.05),rgba(239,68,68,.05))}
.dhd .dn{font-family:'Space Mono',monospace;font-size:.58rem;text-transform:uppercase;letter-spacing:.1em;display:block;margin-bottom:3px}
.dhd.q0 .dn{color:var(--cy)}.dhd.q1 .dn{color:var(--pu)}.dhd.q2 .dn{color:var(--am)}
.dbd{display:grid;grid-template-columns:1.2fr .8fr;min-height:200px}
.dwc{padding:14px;border-right:1px solid var(--bd);display:flex;align-items:center;justify-content:center}
.dwc svg{width:100%;height:auto}
.dst{padding:14px;display:flex;flex-direction:column;gap:12px}
.dsr{display:flex;gap:6px}
.dsb{flex:1;text-align:center;padding:10px 4px;border-radius:var(--rs);background:var(--c2)}
.dsb .n{font-size:1.3rem;font-weight:700;display:block}.dsb .l{font-size:.58rem;font-family:'Space Mono',monospace;color:var(--t3)}
.dsb.gn .n{color:var(--gn)}.dsb.am .n{color:var(--am)}.dsb.rd .n{color:var(--rd)}
.dav{font-family:'Space Mono',monospace;font-size:.65rem;color:var(--t3);text-align:center}
.dfd{flex:1;overflow-y:auto;max-height:120px}
.dfi{font-size:.7rem;color:var(--t2);padding:3px 0;border-bottom:1px solid var(--bd);line-height:1.3}

/* ═══ TURING TEST TAB ═══ */
.tt-wrap{padding:24px 28px;max-width:1100px;margin:0 auto}
.tt-grid{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-top:16px}
.tt-qr{text-align:center;padding:20px;border-radius:var(--r);border:1px dashed rgba(236,72,153,.3);background:linear-gradient(135deg,rgba(236,72,153,.04),rgba(168,85,247,.04))}
.tt-qr img{border-radius:8px;max-width:180px}
.tt-qr p{font-size:.78rem;color:var(--t2);margin-top:8px}
.tt-hero{display:flex;gap:12px;margin-bottom:16px}
.tt-big{flex:1;text-align:center;padding:18px 8px;border-radius:var(--r);border:1px solid var(--bd);background:var(--c1)}
.tt-big .n{font-size:2.4rem;font-weight:700;display:block}
.tt-big .l{font-size:.62rem;font-family:'Space Mono',monospace;color:var(--t3)}
.tt-big.acc .n{color:var(--gn)}.tt-big.tot .n{color:var(--cy)}.tt-big.fool .n{color:var(--rd)}

/* accuracy bars */
.acc-bar-wrap{margin-bottom:8px}
.acc-bar-label{display:flex;justify-content:space-between;font-size:.72rem;margin-bottom:3px}
.acc-bar-label span:first-child{color:var(--t2)}.acc-bar-label span:last-child{font-weight:700;font-family:'Space Mono',monospace}
.acc-bar-track{height:8px;border-radius:4px;background:var(--c2);overflow:hidden}
.acc-bar-fill{height:100%;border-radius:4px;transition:width .6s}

/* ratings display */
.rat-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.rat-item{text-align:center;padding:10px;border-radius:var(--rs);background:var(--c2)}
.rat-item .n{font-size:1.5rem;font-weight:700;display:block;color:var(--am)}
.rat-item .l{font-size:.6rem;font-family:'Space Mono',monospace;color:var(--t3)}

/* task bars */
.task-row{display:flex;align-items:center;gap:8px;margin-bottom:6px}
.task-name{font-size:.72rem;color:var(--t2);width:140px;text-align:right;flex-shrink:0}
.task-bar{flex:1;height:6px;border-radius:3px;background:var(--c2);overflow:hidden}
.task-fill{height:100%;border-radius:3px;background:linear-gradient(90deg,var(--pk),var(--pu));transition:width .6s}
.task-n{font-size:.65rem;font-family:'Space Mono',monospace;color:var(--t3);width:30px}

.adm{padding:8px 28px;border-top:1px solid var(--bd);display:flex;justify-content:space-between;align-items:center;background:var(--bg)}
.adm .tc{font-family:'Space Mono',monospace;font-size:.68rem;color:var(--t3)}

.no-speech{background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.3);color:#fca5a5;padding:8px 12px;border-radius:var(--rs);font-size:.75rem;text-align:center;display:none}
.no-speech.vis{display:block}

#qlive_0,#qlive_1,#qlive_2{border-color:rgba(34,197,94,.3);background:linear-gradient(135deg,rgba(34,197,94,.03),rgba(6,182,212,.03))}
#qlive_0.active,#qlive_1.active,#qlive_2.active{border-color:rgba(34,197,94,.6);box-shadow:0 0 12px rgba(34,197,94,.1);animation:livePulse 2s infinite}
#qlive_0 h3,#qlive_1 h3,#qlive_2 h3{color:var(--gn)}
@keyframes livePulse{0%,100%{box-shadow:0 0 8px rgba(34,197,94,.1)}50%{box-shadow:0 0 18px rgba(34,197,94,.2)}}

@keyframes fi{from{opacity:0}to{opacity:1}}
@keyframes si{from{opacity:0;transform:translateY(5px)}to{opacity:1;transform:translateY(0)}}
@media(max-width:900px){.ip,.ov-grid,.dbd,.tt-grid{grid-template-columns:1fr}.ov-wc-row{grid-template-columns:1fr}.ip-l{border-right:none;border-bottom:1px solid var(--bd)}.dwc{border-right:none;border-bottom:1px solid var(--bd)}.pqg{grid-template-columns:1fr}.ts-grid{grid-template-columns:repeat(2,1fr)}}
</style></head><body>

<header class="hdr"><h1>{{ title }}</h1><div class="pills"><span class="pill" id="totPill">0 responses</span><span class="pill" id="ttPill" style="border-color:var(--pk);color:var(--pk)">0 survey</span><span class="pill on" id="stPill">● Ready</span></div></header>

<nav class="tabs">
<button class="tab ov on" onclick="go('ov')">📊 Live Overview</button>
<button class="tab" onclick="go('q0')">Q1 — Input</button>
<button class="tab" onclick="go('q1')">Q2 — Input</button>
<button class="tab" onclick="go('q2')">Q3 — Input</button>
<button class="tab dt" onclick="go('dash')">Per-Question Dashboard</button>
<button class="tab tt" onclick="go('turing')">🤖 AI vs Human</button>
</nav>

<!-- ══════ OVERVIEW ══════ -->
<div class="pnl on" id="pnl_ov"><div class="ov-wrap">
<div class="ov-title"><b>Live Overview</b> — All responses · <span style="font-size:.7rem;color:var(--t3)">Auto-refreshes every 3s</span></div>

<!-- 3 per-question word clouds -->
<div class="ov-wc-row">
  <div class="ov-wc-card q0"><h3 style="color:var(--cy)">Q1 Word Cloud</h3><div class="qtext">{{ questions[0] }}</div><div class="ov-wc" id="ovWC0"><div class="ov-empty" style="padding:20px;font-size:.8rem">No Q1 responses yet</div></div></div>
  <div class="ov-wc-card q1"><h3 style="color:var(--pu)">Q2 Word Cloud</h3><div class="qtext">{{ questions[1] }}</div><div class="ov-wc" id="ovWC1"><div class="ov-empty" style="padding:20px;font-size:.8rem">No Q2 responses yet</div></div></div>
  <div class="ov-wc-card q2"><h3 style="color:var(--am)">Q3 Word Cloud</h3><div class="qtext">{{ questions[2] }}</div><div class="ov-wc" id="ovWC2"><div class="ov-empty" style="padding:20px;font-size:.8rem">No Q3 responses yet</div></div></div>
</div>

<div class="ov-grid" style="margin-top:20px">
  <div class="ov-card">
    <h3>Overall Sentiment</h3>
    <div class="big3"><div class="b3 gn"><span class="n" id="ovPos">0</span><span class="l">Positive</span></div><div class="b3 am"><span class="n" id="ovNeu">0</span><span class="l">Neutral</span></div><div class="b3 rd"><span class="n" id="ovNeg">0</span><span class="l">Negative</span></div></div>
    <div class="avg" id="ovAvg">Avg polarity: 0 · Total: 0</div>
    <h3 style="margin-top:10px">Per-Question Breakdown</h3>
    <div class="pqg" id="ovPQ"></div>
  </div>
</div>
<!-- Turing test snapshot on overview -->
<div class="ts-card" id="ovTuring">
  <h3>🤖 AI vs Human — Turing Test Snapshot</h3>
  <div class="ts-grid" id="ovTuringGrid">
    <div class="ts-stat"><span class="n" id="ovTtot">0</span><span class="l">Respondents</span></div>
    <div class="ts-stat"><span class="n" id="ovTacc">0%</span><span class="l">Accuracy</span></div>
    <div class="ts-stat"><span class="n" id="ovTfooled">0%</span><span class="l">Fooled by AI</span></div>
    <div class="ts-stat"><span class="n" id="ovTrat">—</span><span class="l">Avg Trust</span></div>
  </div>
  <div class="avg" style="margin-top:8px"><a href="/survey" target="_blank" style="color:var(--pk);text-decoration:underline">Open standalone survey ↗</a> · <a href="/qr" target="_blank" style="color:var(--pk);text-decoration:underline">QR Code ↗</a></div>
</div>
</div></div>

<!-- ══════ Q INPUTS ══════ -->
{% for i in range(3) %}
<div class="pnl" id="pnl_q{{i}}"><div class="ip">
<div class="ip-l">
  <div class="qban q{{i}}"><span class="qn">Question {{i+1}} of 3</span>{{ questions[i] }}</div>
  <div class="no-speech" id="noSp_{{i}}">⚠ Your browser doesn't support live speech recognition. Please use Chrome/Edge, or type manually below.</div>
  <div class="ma">
    <button class="mb" id="mic_{{i}}" onclick="toggleSpeech({{i}})"><svg viewBox="0 0 24 24"><path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm5.91-3c-.49 0-.9.36-.98.85C16.52 14.2 14.47 16 12 16s-4.52-1.8-4.93-4.15c-.08-.49-.49-.85-.98-.85-.61 0-1.09.54-1 1.14.49 3 2.89 5.35 5.91 5.78V20c0 .55.45 1 1 1s1-.45 1-1v-2.08c3.02-.43 5.42-2.78 5.91-5.78.1-.6-.39-1.14-1-1.14z"/></svg></button>
    <span class="ml" id="ml_{{i}}">Tap to start live transcription</span>
  </div>
  <textarea class="tx" id="tx_{{i}}" placeholder="Speech appears here in real time, or type manually..." rows="3"></textarea>
  <div class="br"><button class="btn bp" id="sub_{{i}}" onclick="sub({{i}})">Submit</button><button class="btn bg" onclick="clr({{i}})">Clear</button></div>
  <div class="lr" id="lr_{{i}}"><div class="lr-top"><span class="lr-em" id="lrem_{{i}}"></span><div><div class="lr-lb" id="lrlb_{{i}}"></div><div class="lr-pl" id="lrpl_{{i}}"></div></div></div><div class="lr-bar"><div class="lr-fill" id="lrf_{{i}}"></div></div></div>
</div>
<div class="ip-r">
  <div class="card" id="qlive_{{i}}"><h3>🔴 Live Preview — Speaking Now</h3><div class="wci" id="qlwci_{{i}}"><div class="ov-empty" style="padding:20px">Start speaking or typing to see words appear...</div></div></div>
  <div class="emp" id="qemp_{{i}}">No submitted responses for Q{{i+1}} yet.</div>
  <div class="card" id="qwcc_{{i}}" style="display:none"><h3>Word Cloud — Q{{i+1}} (Submitted)</h3><div class="wci" id="qwci_{{i}}"></div></div>
  <div class="card" id="qstc_{{i}}" style="display:none"><h3>Sentiment — Q{{i+1}}</h3>
    <div class="sbs">
      <div class="sbc"><span class="sbn" id="qpos_{{i}}" style="color:var(--gn)">0</span><div class="sbt"><div class="sbf" id="qposf_{{i}}" style="background:var(--gn);height:0%"></div></div><span class="sbl">Pos</span></div>
      <div class="sbc"><span class="sbn" id="qneu_{{i}}" style="color:var(--am)">0</span><div class="sbt"><div class="sbf" id="qneuf_{{i}}" style="background:var(--am);height:0%"></div></div><span class="sbl">Neu</span></div>
      <div class="sbc"><span class="sbn" id="qneg_{{i}}" style="color:var(--rd)">0</span><div class="sbt"><div class="sbf" id="qnegf_{{i}}" style="background:var(--rd);height:0%"></div></div><span class="sbl">Neg</span></div>
    </div>
  </div>
  <div class="card" id="qfdc_{{i}}" style="display:none"><h3>Recent — Q{{i+1}}</h3><div class="fd" id="qfd_{{i}}"></div></div>
</div>
</div></div>
{% endfor %}

<!-- ══════ FULL DASHBOARD ══════ -->
<div class="pnl" id="pnl_dash"><div class="dg" id="dashG"></div></div>

<!-- ══════ TURING TEST DASHBOARD ══════ -->
<div class="pnl" id="pnl_turing"><div class="tt-wrap">
<div class="ov-title"><b style="color:var(--pk)">🤖 AI vs Human</b> — Can clinicians tell the difference? · <span style="font-size:.7rem;color:var(--t3)">Auto-refreshes every 3s</span></div>

<!-- QR + hero stats -->
<div class="tt-hero">
  <div class="tt-big tot"><span class="n" id="ttTot">0</span><span class="l">Total Respondents</span></div>
  <div class="tt-big acc"><span class="n" id="ttAcc">0%</span><span class="l">Overall Accuracy</span></div>
  <div class="tt-big fool"><span class="n" id="ttFool">0%</span><span class="l">Fooled by AI</span></div>
</div>

<div class="tt-grid">
  <!-- Left: Accuracy by group -->
  <div class="ov-card">
    <h3>Accuracy by Job Group</h3>
    <div id="ttJobBars"><div class="ov-empty">No responses yet</div></div>
  </div>
  <div class="ov-card">
    <h3>Accuracy by Seniority</h3>
    <div id="ttSenBars"><div class="ov-empty">No responses yet</div></div>
    <h3 style="margin-top:16px">Average AI Ratings (1–5)</h3>
    <div class="rat-grid" id="ttRatings">
      <div class="rat-item"><span class="n">—</span><span class="l">Trust</span></div>
      <div class="rat-item"><span class="n">—</span><span class="l">Empathy</span></div>
      <div class="rat-item"><span class="n">—</span><span class="l">Safety</span></div>
      <div class="rat-item"><span class="n">—</span><span class="l">Usefulness</span></div>
    </div>
  </div>
  <div class="ov-card">
    <h3>Accuracy by Scenario</h3>
    <div id="ttScBars"><div class="ov-empty">No responses yet</div></div>
  </div>
  <div class="ov-card">
    <h3>Tasks Respondents Would Allow AI to Do</h3>
    <div id="ttTasks"><div class="ov-empty">No responses yet</div></div>
    <div style="margin-top:16px">
      <h3>QR Code — Standalone Survey</h3>
      <div class="tt-qr"><img src="/qr" alt="QR code to survey"><p>Scan to take the survey on your phone</p><p style="font-size:.65rem;color:var(--t3)"><a href="/survey" target="_blank" style="color:var(--pk)">/survey</a></p></div>
    </div>
  </div>
</div>
</div></div>

<div class="adm"><span class="tc" id="totC">Total: 0 responses · 0 survey</span><div style="display:flex;gap:6px"><button class="btn bg" onclick="exp()" style="font-size:.7rem;padding:5px 10px">Export JSON</button><button class="btn bg" onclick="rst()" style="font-size:.7rem;padding:5px 10px;color:var(--rd)">Reset All</button></div></div>

<script>
const QS={{questions|tojson}},QN=3;
const STOP={{stop_words|tojson}};
const STOP_SET=new Set(STOP);

// ════════════════════════════════════════════════════════
// D3 WORD CLOUD RENDERER
// ════════════════════════════════════════════════════════
const WC_COLORS=["#06b6d4","#3b82f6","#a855f7","#ec4899","#22c55e","#f59e0b","#f97316","#14b8a6","#8b5cf6","#6366f1"];

function renderWordCloud(container, words, w, h){
  container.innerHTML='';
  if(!words||!words.length){container.innerHTML='<div class="ov-empty">No words yet</div>';return}
  w=w||600; h=h||300;
  const maxVal=d3.max(words,d=>d.value)||1;
  const sizeScale=d3.scaleSqrt().domain([1,maxVal]).range([14,w>500?70:50]);
  d3.layout.cloud().size([w,h])
    .words(words.map(d=>({text:d.text,size:sizeScale(d.value),value:d.value})))
    .padding(3).rotate(()=>(~~(Math.random()*3)-1)*30)
    .font("'DM Sans', sans-serif").fontSize(d=>d.size).spiral("archimedean")
    .on("end",function(placed){
      const svg=d3.select(container).append("svg").attr("viewBox",`0 0 ${w} ${h}`).attr("width","100%").attr("height","100%");
      const g=svg.append("g").attr("transform",`translate(${w/2},${h/2})`);
      g.selectAll("text").data(placed).enter().append("text")
        .style("font-size",d=>d.size+"px").style("font-family","'DM Sans', sans-serif")
        .style("font-weight",d=>d.size>40?"700":"500")
        .style("fill",(d,i)=>WC_COLORS[i%WC_COLORS.length]).style("opacity",0)
        .attr("text-anchor","middle").attr("transform",d=>`translate(${d.x},${d.y})rotate(${d.rotate})`)
        .text(d=>d.text).transition().duration(400).delay((d,i)=>i*15).style("opacity",.9);
    }).start();
}

function extractWordsClient(text){
  const cleaned=text.toLowerCase().replace(/[^a-zA-Z\s]/g,'');
  const words=cleaned.split(/\s+/).filter(w=>w.length>2&&!STOP_SET.has(w));
  const freq={};words.forEach(w=>{freq[w]=(freq[w]||0)+1});
  return Object.entries(freq).sort((a,b)=>b[1]-a[1]).slice(0,60).map(([text,value])=>({text,value}));
}

let liveTimers=[null,null,null];
function updateLivePreview(q){
  if(liveTimers[q])clearTimeout(liveTimers[q]);
  liveTimers[q]=setTimeout(()=>{
    const text=$(`tx_${q}`).value.trim();const container=$(`qlwci_${q}`);const card=$(`qlive_${q}`);
    if(!text){container.innerHTML='<div class="ov-empty" style="padding:20px">Start speaking or typing to see words appear...</div>';card.classList.remove('active');return}
    const words=extractWordsClient(text);
    if(!words.length){container.innerHTML='<div class="ov-empty" style="padding:20px">Listening... (waiting for content words)</div>';card.classList.add('active');return}
    card.classList.add('active');renderWordCloud(container,words,600,320);
  },400);
}

// ════════════════════════════════════════════════════════
// WEB SPEECH API
// ════════════════════════════════════════════════════════
const SpeechRecognition=window.SpeechRecognition||window.webkitSpeechRecognition;
const HAS_SPEECH=!!SpeechRecognition;
let speechInstances=Array.from({length:QN},()=>null);
let speechActive=Array.from({length:QN},()=>false);
// ► Persistent transcript storage per question — survives recognition restarts
let finalTranscripts=Array.from({length:QN},()=>'');

function toggleSpeech(q){if(!HAS_SPEECH){$(`noSp_${q}`).classList.add('vis');return}speechActive[q]?stopSpeech(q):startSpeech(q)}

function startSpeech(q){
  for(let i=0;i<QN;i++){if(i!==q&&speechActive[i])stopSpeech(i)}
  // Seed from whatever is already in the textarea (manual typing before mic)
  finalTranscripts[q]=$(`tx_${q}`).value;
  _launchRecognition(q);
}

function _launchRecognition(q){
  const recognition=new SpeechRecognition();recognition.continuous=true;recognition.interimResults=true;recognition.lang='en-US';recognition.maxAlternatives=1;

  recognition.onresult=(event)=>{
    let interim='';
    for(let i=event.resultIndex;i<event.results.length;i++){
      const transcript=event.results[i][0].transcript;
      if(event.results[i].isFinal){
        finalTranscripts[q]+=transcript+' ';
      }else{
        interim+=transcript;
      }
    }
    $(`tx_${q}`).value=finalTranscripts[q]+interim;
    $(`tx_${q}`).scrollTop=$(`tx_${q}`).scrollHeight;
    updateLivePreview(q);
  };

  recognition.onerror=(e)=>{
    if(e.error==='not-allowed'){$(`ml_${q}`).textContent='Mic permission denied';stopSpeech(q)}
    else if(e.error!=='no-speech'&&e.error!=='aborted'){
      // On transient errors, restart cleanly
      if(speechActive[q]){setTimeout(()=>{if(speechActive[q])_launchRecognition(q)},300)}
    }
  };

  recognition.onend=()=>{
    // Chrome caps continuous recognition at ~60s — restart with accumulated transcript intact
    if(speechActive[q]){setTimeout(()=>{if(speechActive[q])_launchRecognition(q)},100)}
  };

  try{
    recognition.start();speechInstances[q]=recognition;speechActive[q]=true;
    $(`mic_${q}`).classList.add('rec');$(`tx_${q}`).classList.add('listening');
    $(`ml_${q}`).textContent='🔴 Listening... words appear live — tap to stop';
    $(`ml_${q}`).classList.add('live');setS('Listening','var(--gn)');
  }catch(e){console.error(e)}
}

function stopSpeech(q){
  speechActive[q]=false;
  if(speechInstances[q]){try{speechInstances[q].stop()}catch(e){}speechInstances[q]=null}
  $(`mic_${q}`).classList.remove('rec');$(`tx_${q}`).classList.remove('listening');$(`ml_${q}`).textContent='Tap to start live transcription';$(`ml_${q}`).classList.remove('live');setS('Ready','var(--gn)');
}

// ════════════════════════════════════════════════════════
// CORE HELPERS
// ════════════════════════════════════════════════════════
function $(id){return document.getElementById(id)}
function setS(t,c){let p=$('stPill');p.textContent='● '+t;p.style.borderColor=c;p.style.color=c}

let currentPanel='ov';
function go(id){
  currentPanel=id;
  document.querySelectorAll('.pnl').forEach(p=>p.classList.remove('on'));
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('on'));
  $('pnl_'+id).classList.add('on');
  let tabs=document.querySelectorAll('.tab');
  let m={ov:0,q0:1,q1:2,q2:3,dash:4,turing:5};
  if(m[id]!==undefined)tabs[m[id]].classList.add('on');
  if(id==='ov')loadOv();else if(id==='dash')loadDash();else if(id==='turing')loadTuring();
  else loadQ(+id.replace('q',''));
}

async function sub(q){
  let bx=$(`tx_${q}`),t=bx.value.trim();if(!t)return;
  if(speechActive[q])stopSpeech(q);$(`sub_${q}`).disabled=true;
  try{let x=await(await fetch('/api/submit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:t,question_index:q})})).json();
    if(x.entry){showLR(q,x.entry.sentiment);loadQ(q);bx.value='';finalTranscripts[q]='';updTot();updateLivePreview(q)}}catch(e){console.error(e)}
  $(`sub_${q}`).disabled=false;
}

function showLR(q,s){$(`lrem_${q}`).textContent=s.emoji;$(`lrlb_${q}`).textContent=s.label;$(`lrlb_${q}`).style.color=s.color;$(`lrpl_${q}`).textContent='Polarity: '+s.polarity;let f=$(`lrf_${q}`);f.style.width=((s.polarity+1)/2*100)+'%';f.style.background=s.color;$(`lr_${q}`).classList.add('vis')}
function clr(q){$(`tx_${q}`).value='';finalTranscripts[q]='';$(`lr_${q}`).classList.remove('vis');if(speechActive[q])stopSpeech(q);updateLivePreview(q)}

async function loadQ(q){
  try{let d=await(await fetch(`/api/q/${q}`)).json();
    if(d.stats.total===0){$(`qemp_${q}`).style.display='block';$(`qwcc_${q}`).style.display='none';$(`qstc_${q}`).style.display='none';$(`qfdc_${q}`).style.display='none';return}
    $(`qemp_${q}`).style.display='none';$(`qwcc_${q}`).style.display='block';$(`qstc_${q}`).style.display='block';$(`qfdc_${q}`).style.display='block';
    renderWordCloud($(`qwci_${q}`),d.words,600,320);
    let t=d.stats.total||1;$(`qpos_${q}`).textContent=d.stats.positive;$(`qneu_${q}`).textContent=d.stats.neutral;$(`qneg_${q}`).textContent=d.stats.negative;
    $(`qposf_${q}`).style.height=(d.stats.positive/t*100)+'%';$(`qneuf_${q}`).style.height=(d.stats.neutral/t*100)+'%';$(`qnegf_${q}`).style.height=(d.stats.negative/t*100)+'%';
    $(`qfd_${q}`).innerHTML=[...d.entries].reverse().map(e=>`<div class="fdi" style="border-left-color:${e.sentiment.color}">${e.text.substring(0,150)}${e.text.length>150?'...':''}<span class="fs" style="color:${e.sentiment.color}">${e.sentiment.emoji} ${e.sentiment.label} (${e.sentiment.polarity})</span></div>`).join('')
  }catch(e){console.error('loadQ error:',e)}
}

async function loadOv(){
  try{let d=await(await fetch('/api/all')).json(),a=d.agg;
    // Per-question word clouds
    for(let i=0;i<QN;i++){
      let qd=d[String(i)];
      let wc=$('ovWC'+i);
      if(qd.stats.total===0){
        wc.innerHTML='<div class="ov-empty" style="padding:20px;font-size:.8rem">No Q'+(i+1)+' responses yet</div>';
      }else{
        renderWordCloud(wc,qd.words,380,240);
      }
    }
    $('ovPos').textContent=a.stats.positive;$('ovNeu').textContent=a.stats.neutral;$('ovNeg').textContent=a.stats.negative;
    $('ovAvg').textContent=`Avg polarity: ${a.stats.avg_polarity} · Total: ${a.stats.total}`;
    let h='';for(let i=0;i<QN;i++){let s=d[String(i)].stats;h+=`<div class="pqb q${i}"><h4>Q${i+1} · ${s.total} responses</h4><div class="pqn"><span class="g">${s.positive}</span><span class="a">${s.neutral}</span><span class="r">${s.negative}</span></div><div class="pqt">Avg: ${s.avg_polarity}</div></div>`}
    $('ovPQ').innerHTML=h;
    // Turing snapshot
    let tt=d.turing;
    $('ovTtot').textContent=tt.total_respondents;
    $('ovTacc').textContent=tt.overall_accuracy+'%';
    $('ovTfooled').textContent=tt.total_respondents>0?Math.round(100-tt.overall_accuracy)+'%':'0%';
    $('ovTrat').textContent=tt.avg_ratings&&tt.avg_ratings.trust?tt.avg_ratings.trust.toFixed(1):'—';
  }catch(e){console.error('loadOv error:',e)}
}

async function loadDash(){
  try{let d=await(await fetch('/api/all')).json(),g=$('dashG'),h='';
    for(let q=0;q<QN;q++){let x=d[String(q)],ok=x.stats.total>0;
      h+=`<div class="dblk"><div class="dhd q${q}"><span class="dn">Question ${q+1} — ${x.stats.total} responses</span>${QS[q]}</div><div class="dbd"><div class="dwc" id="dwc_${q}">${ok?'':'<div class="ov-empty">No responses</div>'}</div><div class="dst"><div class="dsr"><div class="dsb gn"><span class="n">${x.stats.positive}</span><span class="l">Positive</span></div><div class="dsb am"><span class="n">${x.stats.neutral}</span><span class="l">Neutral</span></div><div class="dsb rd"><span class="n">${x.stats.negative}</span><span class="l">Negative</span></div></div><div class="dav">Avg polarity: ${x.stats.avg_polarity} · Total: ${x.stats.total}</div>${ok?`<div class="dfd">${[...x.entries].reverse().slice(0,5).map(e=>`<div class="dfi"><span style="color:${e.sentiment.color}">${e.sentiment.emoji}</span> ${e.text.substring(0,100)}${e.text.length>100?'...':''}</div>`).join('')}</div>`:''}</div></div></div>`}
    g.innerHTML=h;
    for(let q=0;q<QN;q++){let x=d[String(q)];if(x.stats.total>0&&x.words.length)renderWordCloud(document.getElementById(`dwc_${q}`),x.words,450,220)}
  }catch(e){console.error('loadDash error:',e)}
}

// ════════════════════════════════════════════════════════
// TURING TEST DASHBOARD RENDERER
// ════════════════════════════════════════════════════════
function makeAccBar(label,accuracy,color){
  return `<div class="acc-bar-wrap"><div class="acc-bar-label"><span>${label}</span><span style="color:${color}">${accuracy}%</span></div><div class="acc-bar-track"><div class="acc-bar-fill" style="width:${accuracy}%;background:${color}"></div></div></div>`;
}

async function loadTuring(){
  try{
    let d=await(await fetch('/api/turing/stats')).json();
    $('ttTot').textContent=d.total_respondents;
    $('ttAcc').textContent=d.overall_accuracy+'%';
    $('ttFool').textContent=d.total_respondents>0?Math.round(100-d.overall_accuracy)+'%':'0%';

    // Job group bars
    let jbHTML='';
    if(Object.keys(d.by_job_group).length){
      for(let [k,v] of Object.entries(d.by_job_group)){
        let c=v.accuracy>=60?'#22c55e':v.accuracy>=40?'#f59e0b':'#ef4444';
        jbHTML+=makeAccBar(`${k} (n=${v.total})`,v.accuracy,c);
      }
    }else{jbHTML='<div class="ov-empty" style="padding:15px">No responses yet</div>'}
    $('ttJobBars').innerHTML=jbHTML;

    // Seniority bars
    let snHTML='';
    if(Object.keys(d.by_seniority).length){
      for(let [k,v] of Object.entries(d.by_seniority)){
        let c=v.accuracy>=60?'#22c55e':v.accuracy>=40?'#f59e0b':'#ef4444';
        snHTML+=makeAccBar(`${k} (n=${v.total})`,v.accuracy,c);
      }
    }else{snHTML='<div class="ov-empty" style="padding:15px">No responses yet</div>'}
    $('ttSenBars').innerHTML=snHTML;

    // Ratings
    if(d.avg_ratings && d.total_respondents>0){
      $('ttRatings').innerHTML=`
        <div class="rat-item"><span class="n">${d.avg_ratings.trust.toFixed(1)}</span><span class="l">Trust</span></div>
        <div class="rat-item"><span class="n">${d.avg_ratings.empathy.toFixed(1)}</span><span class="l">Empathy</span></div>
        <div class="rat-item"><span class="n">${d.avg_ratings.safety.toFixed(1)}</span><span class="l">Safety</span></div>
        <div class="rat-item"><span class="n">${d.avg_ratings.usefulness.toFixed(1)}</span><span class="l">Usefulness</span></div>`;
    }

    // Scenario bars
    let scHTML='';
    if(Object.keys(d.by_scenario).length){
      let scLabels={s1:'S1: Weight loss',s2:'S2: Chest tightness',s3:'S3: Child fever+rash',s4:'S4: Depression',s5:'S5: Medication error'};
      for(let [k,v] of Object.entries(d.by_scenario)){
        let c=v.accuracy>=60?'#22c55e':v.accuracy>=40?'#f59e0b':'#ef4444';
        scHTML+=makeAccBar(`${scLabels[k]||k} (n=${v.total})`,v.accuracy,c);
      }
    }else{scHTML='<div class="ov-empty" style="padding:15px">No responses yet</div>'}
    $('ttScBars').innerHTML=scHTML;

    // Tasks
    let tkHTML='';
    if(Object.keys(d.trust_tasks).length){
      let maxT=Math.max(...Object.values(d.trust_tasks));
      for(let [k,v] of Object.entries(d.trust_tasks)){
        tkHTML+=`<div class="task-row"><span class="task-name">${k}</span><div class="task-bar"><div class="task-fill" style="width:${v/maxT*100}%"></div></div><span class="task-n">${v}</span></div>`;
      }
    }else{tkHTML='<div class="ov-empty" style="padding:15px">No responses yet</div>'}
    $('ttTasks').innerHTML=tkHTML;

  }catch(e){console.error('loadTuring error:',e)}
}


async function updTot(){
  try{let d=await(await fetch('/api/all')).json(),t=d.agg.stats.total,tt=d.turing.total_respondents;
    $('totPill').textContent=t+' responses';$('ttPill').textContent=tt+' survey';
    $('totC').textContent=`Total: ${t} responses · ${tt} survey respondents`;
  }catch(e){}
}

async function rst(){if(!confirm('Reset ALL data (sentiment + survey)?'))return;await fetch('/api/reset',{method:'POST'});for(let q=0;q<QN;q++)loadQ(q);loadOv();loadDash();loadTuring();updTot()}

async function exp(){let d=await(await fetch('/api/export')).json();let b=new Blob([JSON.stringify(d,null,2)],{type:'application/json'});let u=URL.createObjectURL(b),a=document.createElement('a');a.href=u;a.download=`sentiment_export_${new Date().toISOString().slice(0,10)}.json`;a.click();URL.revokeObjectURL(u)}

setInterval(()=>{
  if(currentPanel==='ov')loadOv();
  else if(currentPanel==='dash')loadDash();
  else if(currentPanel==='turing')loadTuring();
  else if(currentPanel.startsWith('q'))loadQ(+currentPanel.replace('q',''));
  updTot();
},3000);

if(!HAS_SPEECH){for(let i=0;i<QN;i++)$(`noSp_${i}`).classList.add('vis')}
for(let q=0;q<QN;q++){$(`tx_${q}`).addEventListener('input',()=>updateLivePreview(q))}
updTot();loadOv();
</script></body></html>"""


# ═══════════════════════════════════════════════════════
# STANDALONE SURVEY TEMPLATE (mobile-friendly, QR accessible)
# ═══════════════════════════════════════════════════════
SURVEY_TMPL = r"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ title }} — AI vs Human Survey</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
:root{--bg:#0a0e1a;--c1:#111827;--c2:#1a2235;--bd:#1e293b;--t1:#f1f5f9;--t2:#94a3b8;--t3:#64748b;
--bl:#3b82f6;--cy:#06b6d4;--gn:#22c55e;--rd:#ef4444;--am:#f59e0b;--pu:#a855f7;--pk:#ec4899;--r:12px;--rs:8px}
*{margin:0;padding:0;box-sizing:border-box}body{font-family:'DM Sans',sans-serif;background:var(--bg);color:var(--t1);min-height:100vh}
.wrap{max-width:640px;margin:0 auto;padding:16px}
.hdr{text-align:center;padding:20px 0 16px;border-bottom:1px solid var(--bd);margin-bottom:20px}
.hdr h1{font-size:1.2rem;font-weight:700;background:linear-gradient(135deg,var(--pk),var(--pu));-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.hdr p{font-size:.8rem;color:var(--t2);margin-top:6px}
.step{display:none}.step.on{display:block;animation:fi .3s}
@keyframes fi{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
.card{border-radius:var(--r);border:1px solid var(--bd);background:var(--c1);padding:16px;margin-bottom:14px}
.card h3{font-size:.72rem;font-family:'Space Mono',monospace;text-transform:uppercase;letter-spacing:.08em;color:var(--pk);margin-bottom:10px}
.card h4{font-size:.82rem;font-weight:500;margin-bottom:8px;color:var(--t2)}
.patient-box{padding:12px;border-radius:var(--rs);background:linear-gradient(135deg,rgba(59,130,246,.06),rgba(6,182,212,.06));border:1px solid rgba(59,130,246,.15);font-size:.88rem;line-height:1.6;margin-bottom:12px}
.patient-box .icon{font-size:1.2rem;margin-right:6px}
.resp-option{padding:12px;border-radius:var(--rs);border:2px solid var(--bd);background:var(--c2);cursor:pointer;margin-bottom:8px;font-size:.84rem;line-height:1.5;transition:.2s}
.resp-option:hover{border-color:var(--bl)}
.resp-option.sel{border-color:var(--pk);background:rgba(236,72,153,.08)}
.resp-option .tag{font-family:'Space Mono',monospace;font-size:.6rem;color:var(--t3);display:block;margin-bottom:4px}

/* ratings */
.rating-row{display:flex;align-items:center;gap:8px;margin-bottom:10px}
.rating-label{font-size:.78rem;width:90px;color:var(--t2)}
.stars{display:flex;gap:4px}
.star{width:30px;height:30px;border-radius:4px;background:var(--c2);border:1px solid var(--bd);cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:.9rem;transition:.2s}
.star:hover{background:rgba(236,72,153,.15);border-color:var(--pk)}
.star.on{background:rgba(236,72,153,.2);border-color:var(--pk);color:var(--pk)}

/* select options */
.sel-group{display:flex;flex-direction:column;gap:6px;margin-bottom:14px}
.sel-group label{font-size:.82rem;color:var(--t2);margin-bottom:2px}
.sel-opt{padding:10px 12px;border-radius:var(--rs);border:1px solid var(--bd);background:var(--c2);cursor:pointer;font-size:.8rem;transition:.2s}
.sel-opt:hover{border-color:var(--bl)}.sel-opt.sel{border-color:var(--pk);background:rgba(236,72,153,.08)}

.check-group{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}
.chk{padding:8px 12px;border-radius:20px;border:1px solid var(--bd);background:var(--c2);cursor:pointer;font-size:.75rem;transition:.2s}
.chk:hover{border-color:var(--bl)}.chk.sel{border-color:var(--pu);background:rgba(168,85,247,.12);color:var(--pu)}

.btn{font-family:'DM Sans',sans-serif;font-size:.85rem;font-weight:600;padding:12px 24px;border-radius:var(--rs);border:none;cursor:pointer;transition:.2s;width:100%}
.bp{background:linear-gradient(135deg,var(--pk),var(--pu));color:#fff}.bp:hover{opacity:.9}.bp:disabled{opacity:.4;cursor:not-allowed}
.bg{background:0;border:1px solid var(--bd);color:var(--t2);margin-top:8px}.bg:hover{background:var(--c2)}

.progress{display:flex;gap:4px;justify-content:center;margin-bottom:16px}
.pdot{width:8px;height:8px;border-radius:50%;background:var(--bd)}
.pdot.on{background:var(--pk)}.pdot.done{background:var(--gn)}

/* results */
.result-card{border-radius:var(--r);border:1px solid var(--bd);background:var(--c1);padding:14px;margin-bottom:10px}
.result-card.correct{border-color:rgba(34,197,94,.4);background:rgba(34,197,94,.05)}
.result-card.wrong{border-color:rgba(239,68,68,.4);background:rgba(239,68,68,.05)}
.result-badge{font-family:'Space Mono',monospace;font-size:.65rem;padding:3px 8px;border-radius:10px;display:inline-block;margin-bottom:6px}
.result-badge.correct{background:rgba(34,197,94,.15);color:var(--gn)}.result-badge.wrong{background:rgba(239,68,68,.15);color:var(--rd)}
.result-exp{font-size:.78rem;color:var(--t2);line-height:1.5;margin-top:6px}

.score-hero{text-align:center;padding:20px;margin-bottom:16px}
.score-hero .big{font-size:3rem;font-weight:700;background:linear-gradient(135deg,var(--pk),var(--pu));-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.score-hero .sub{font-size:.85rem;color:var(--t2);margin-top:4px}
</style></head><body>
<div class="wrap">
<div class="hdr"><h1>🤖 AI vs Human — Can You Tell?</h1><p>Read each patient scenario, then guess which response was written by AI</p></div>

<div class="progress" id="progress"></div>

<!-- Step 0: Demographics -->
<div class="step on" id="step_demo">
  <div class="card">
    <h3>About You</h3>
    <div class="sel-group"><label>Your Role / Job Group</label><div id="jg_opts"></div></div>
    <div class="sel-group"><label>Seniority Level</label><div id="sn_opts"></div></div>
  </div>
  <button class="btn bp" onclick="startScenarios()">Start Survey →</button>
</div>

<!-- Steps 1–5: Scenarios (generated by JS) -->
<div id="scenario_steps"></div>

<!-- Final: Tasks + Submit -->
<div class="step" id="step_tasks">
  <div class="card">
    <h3>One Last Question</h3>
    <h4>Which tasks would you be comfortable allowing AI to perform?</h4>
    <p style="font-size:.72rem;color:var(--t3);margin-bottom:8px">Select all that apply</p>
    <div class="check-group" id="task_checks"></div>
  </div>
  <button class="btn bp" onclick="submitAll()">Submit All →</button>
</div>

<!-- Results -->
<div class="step" id="step_results">
  <div class="score-hero" id="scoreHero"></div>
  <div id="resultCards"></div>
  <button class="btn bg" onclick="location.reload()">Take Again</button>
</div>
</div>

<script>
const SCENARIOS={{scenarios_json|safe}};
const JOB_GROUPS={{job_groups|tojson}};
const SENIORITY={{seniority_levels|tojson}};
const TASKS={{trust_tasks|tojson}};

let selJobGroup='',selSeniority='';
let answers={}; // {scenario_id:{guessed_ai_index, ratings:{trust,empathy,safety,usefulness}}}
let selTasks=new Set();
let currentStep=0;
const totalSteps=SCENARIOS.length+2; // demo + scenarios + tasks

function $(id){return document.getElementById(id)}

// Build progress dots
function updateProgress(){
  let h='';for(let i=0;i<totalSteps;i++){
    let cls=i<currentStep?'done':i===currentStep?'on':'';
    h+=`<div class="pdot ${cls}"></div>`;
  }$('progress').innerHTML=h;
}

// Build demographics
function buildDemo(){
  let jh='';JOB_GROUPS.forEach(g=>{jh+=`<div class="sel-opt" onclick="pickJG(this,'${g}')">${g}</div>`});$('jg_opts').innerHTML=jh;
  let sh='';SENIORITY.forEach(s=>{sh+=`<div class="sel-opt" onclick="pickSN(this,'${s}')">${s}</div>`});$('sn_opts').innerHTML=sh;
}

function pickJG(el,v){selJobGroup=v;document.querySelectorAll('#jg_opts .sel-opt').forEach(e=>e.classList.remove('sel'));el.classList.add('sel')}
function pickSN(el,v){selSeniority=v;document.querySelectorAll('#sn_opts .sel-opt').forEach(e=>e.classList.remove('sel'));el.classList.add('sel')}

// Build scenario steps
function buildScenarios(){
  let h='';SCENARIOS.forEach((sc,i)=>{
    h+=`<div class="step" id="step_sc_${i}">
      <div class="card"><h3>Scenario ${i+1} of ${SCENARIOS.length}</h3>
        <div class="patient-box"><span class="icon">🗣️</span> <strong>Patient says:</strong><br>${sc.patient}</div>
        <h4>Which response was written by AI?</h4>
        <div class="resp-option" id="sc${i}_r0" onclick="pickResp(${i},0)"><span class="tag">Response A</span>${sc.responses[0]}</div>
        <div class="resp-option" id="sc${i}_r1" onclick="pickResp(${i},1)"><span class="tag">Response B</span>${sc.responses[1]}</div>
      </div>
      <div class="card" id="sc${i}_ratings" style="display:none">
        <h3>Rate the AI Response</h3>
        <p style="font-size:.72rem;color:var(--t3);margin-bottom:10px">Rate the response you identified as AI (1 = very poor, 5 = excellent)</p>
        <div class="rating-row"><span class="rating-label">Trust</span><div class="stars" id="sc${i}_trust">${makeStars(i,'trust')}</div></div>
        <div class="rating-row"><span class="rating-label">Empathy</span><div class="stars" id="sc${i}_empathy">${makeStars(i,'empathy')}</div></div>
        <div class="rating-row"><span class="rating-label">Safety</span><div class="stars" id="sc${i}_safety">${makeStars(i,'safety')}</div></div>
        <div class="rating-row"><span class="rating-label">Usefulness</span><div class="stars" id="sc${i}_usefulness">${makeStars(i,'usefulness')}</div></div>
      </div>
      <button class="btn bp" onclick="nextScenario(${i})">Next →</button>
    </div>`;
  });
  $('scenario_steps').innerHTML=h;
}

function makeStars(scIdx,dim){
  let h='';for(let s=1;s<=5;s++){h+=`<div class="star" onclick="rate(${scIdx},'${dim}',${s},this)">${s}</div>`}return h;
}

function pickResp(scIdx,rIdx){
  document.querySelectorAll(`#step_sc_${scIdx} .resp-option`).forEach(e=>e.classList.remove('sel'));
  $(`sc${scIdx}_r${rIdx}`).classList.add('sel');
  let sid=SCENARIOS[scIdx].id;
  if(!answers[sid])answers[sid]={guessed_ai_index:rIdx,ratings:{trust:3,empathy:3,safety:3,usefulness:3}};
  else answers[sid].guessed_ai_index=rIdx;
  $(`sc${scIdx}_ratings`).style.display='block';
}

function rate(scIdx,dim,val,el){
  let sid=SCENARIOS[scIdx].id;
  if(!answers[sid])return;
  answers[sid].ratings[dim]=val;
  el.parentElement.querySelectorAll('.star').forEach((s,i)=>{s.classList.toggle('on',i<val)});
}

function goToStep(n){
  currentStep=n;
  document.querySelectorAll('.step').forEach(s=>s.classList.remove('on'));
  if(n===0)$('step_demo').classList.add('on');
  else if(n<=SCENARIOS.length)$(`step_sc_${n-1}`).classList.add('on');
  else if(n===SCENARIOS.length+1)$('step_tasks').classList.add('on');
  else $('step_results').classList.add('on');
  updateProgress();window.scrollTo(0,0);
}

function startScenarios(){
  if(!selJobGroup||!selSeniority){alert('Please select your role and seniority level');return}
  goToStep(1);
}

function nextScenario(scIdx){
  let sid=SCENARIOS[scIdx].id;
  if(!answers[sid]){alert('Please select which response you think is AI');return}
  goToStep(scIdx+2);
}

// Build task checkboxes
function buildTasks(){
  let h='';TASKS.forEach(t=>{h+=`<div class="chk" onclick="toggleTask(this,'${t}')">${t}</div>`});$('task_checks').innerHTML=h;
}

function toggleTask(el,t){el.classList.toggle('sel');if(selTasks.has(t))selTasks.delete(t);else selTasks.add(t)}

async function submitAll(){
  let payload={
    job_group:selJobGroup,seniority:selSeniority,
    answers:Object.entries(answers).map(([sid,a])=>({scenario_id:sid,guessed_ai_index:a.guessed_ai_index,ratings:a.ratings})),
    tasks:[...selTasks]
  };
  try{
    let res=await(await fetch('/api/turing/submit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})).json();
    if(res.ok)showResults(res.results);
    else alert('Error submitting');
  }catch(e){alert('Network error');console.error(e)}
}

function showResults(results){
  let correct=results.filter(r=>r.correct).length;
  let total=results.length;
  let pct=Math.round(correct/total*100);
  let emoji=pct>=80?'🎉':pct>=60?'👍':pct>=40?'🤔':'😱';
  $('scoreHero').innerHTML=`<div class="big">${emoji} ${correct}/${total}</div><div class="sub">You correctly identified ${correct} out of ${total} AI responses (${pct}%)</div>`;

  let h='';results.forEach((r,i)=>{
    let ok=r.correct;
    h+=`<div class="result-card ${ok?'correct':'wrong'}">
      <span class="result-badge ${ok?'correct':'wrong'}">${ok?'✓ Correct':'✗ Incorrect'}</span>
      <strong style="font-size:.82rem"> Scenario ${i+1}</strong>
      <div style="font-size:.72rem;color:var(--t3);margin-top:3px">AI was Response ${r.ai_index===0?'A':'B'}</div>
      <div class="result-exp">${r.explanation}</div>
    </div>`;
  });
  $('resultCards').innerHTML=h;
  goToStep(totalSteps);
}

buildDemo();buildScenarios();buildTasks();updateProgress();
</script></body></html>"""


if __name__ == "__main__":
    print("=" * 60)
    print(f"  {APP_TITLE}  (v4 — with Turing Test)")
    print("=" * 60)
    print(f"  Main app:      http://localhost:5001")
    print(f"  Survey (QR):   http://localhost:5001/survey")
    print(f"  QR Code image: http://localhost:5001/qr")
    print(f"  Questions:     {len(QUESTIONS)}")
    print(f"  Scenarios:     {len(SCENARIOS)}")
    print(f"  Database:      {DB_PATH} (SQLite, persists)")
    print("=" * 60)
    app.run(host="0.0.0.0", port=5001, debug=True)
