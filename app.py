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
from dotenv import load_dotenv
load_dotenv()
from collections import Counter
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, Response, redirect, url_for
from textblob import TextBlob

APP_TITLE = "AI Perspectives — Live Sentiment Booth"
QUESTIONS = [
    "What changes, if any, do you anticipate AI bringing to your work?",
    "What would make you more confident or willing to use AI tools in your daily practice?",
    "What concerns, if any, do you have about the use of AI in healthcare?",
    "How do you think AI could best support — rather than replace — the human elements of healthcare?",
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
# AI ACCEPTANCE SURVEY — CONFIG
# ═══════════════════════════════════════════════════════
ACCEPTANCE_PART_A = {
    "age_group":        ["Under 30", "30–39", "40–49", "50–59", "60 or above"],
    "gender":           ["Male", "Female"],
    "disciplines":      ["Medicine", "Nursing", "Allied Health Professions", "Healthcare Research",
                         "Healthcare Administration & Operations", "Health Informatics & IT", "Other"],
    "years_healthcare": ["Less than 1 year", "1–5 years", "6–10 years", "11–20 years", "More than 20 years"],
    "years_role":       ["Less than 1 year", "1–3 years", "4–7 years", "8–15 years", "More than 15 years"],
    "seniority":        ["Student/Intern/Trainee", "Junior staff", "Mid-level staff",
                         "Senior/Specialist", "Leadership/Director"],
    "ai_frequency":     ["Always", "Often", "Sometimes", "Rarely", "Never"],
    "ai_tools":         ["Commercial AI (ChatGPT, Gemini, Claude)",
                         "Institutional AI (Medivoice, RussellGPT, BotNUHS, Notebuddy, etc.)",
                         "Government AI (Pair, Transcribe, Tandem)",
                         "Clinical Specific AI (AVAT)"],
}

# Likert questions per part. Keys match the JSON keys stored in the DB (e.g. "B1", "C3").
ACCEPTANCE_LIKERT = {
    "B": {
        "title": "AI, Deskilling, and Upskilling",
        "questions": {
            "B1":  "I feel that relying on AI tools could cause healthcare professionals to lose core clinical skills over time.",
            "B2":  "I feel that relying on AI tools could cause healthcare professionals to lose professional communication skills over time.",
            "B3":  "I worry that overreliance on AI recommendations reduces the quality of independent clinical reasoning.",
            "B4":  "I worry that early-career staff may not develop foundational competencies if AI handles too many tasks for them.",
            "B5":  "AI in my department has already changed how much independent thinking is expected of staff.",
            "B6":  "I am concerned that training programmes will adopt AI tools in response to availability rather than at the appropriate stage of a learner's development.",
            "B7":  "I worry that educators are not adequately prepared to teach clinical reasoning skills in environments where AI tools are readily available.",
            "B8":  "As AI tools are introduced into training programmes, I am concerned that trainees will review AI outputs before forming their own clinical assessment.",
            "B9":  "I am concerned that as AI flattens the learning curve, early-career staff would miss opportunities to grapple with complex issues in order to foster adaptive expertise.",
            "B10": "I am concerned that future healthcare providers will over-rely on AI, eroding their ability to develop essential skills like critical thinking, reasoning, and clinical decision-making.",
            "B11": "I believe that AI tools can free up time for me to develop higher-order clinical skills.",
            "B12": "I believe that reviewing AI recommendations can actively sharpen my clinical skills.",
            "B13": "AI has the potential to standardise quality and raise performance across all staff levels.",
            "B14": "I believe that AI assistance helps me focus more on interpersonal interaction and empathy.",
        }
    },
    "C": {
        "title": "Professional Identity and AI",
        "questions": {
            "C1": "I fear that AI will reduce the perceived expertise of healthcare professionals in my discipline in the eyes of the public.",
            "C2": "If AI can perform the tasks I was trained for, my professional standing within healthcare may be undermined.",
            "C3": "I fear that using AI will reduce my autonomy in making clinical or professional decisions.",
            "C4": "Using AI would make it harder for me to fulfil my role as a healthcare provider.",
            "C5": "I feel personally threatened by the idea of AI performing tasks central to my role.",
            "C6": "AI could help me become a more effective and confident healthcare professional.",
            "C7": "The use of AI would allow me to focus on the most meaningful aspects of my role.",
        }
    },
    "D": {
        "title": "Resistance to AI Adoption",
        "questions": {
            "D1": "I do not want AI to change the way I currently work.",
            "D2": "I would prefer to rely on my own professional judgement rather than AI recommendations to make clinical or professional decisions.",
            "D3": "I would feel uncomfortable if AI were to be heavily involved in decisions about my patients or work area.",
            "D4": "I would be more open to using AI if it has been proven to improve patient outcomes or work efficiency.",
            "D5": "If AI could reduce my administrative burden, I would be more open to using it.",
            "D6": "I would be more likely to use AI tools if I could easily see how they benefit my specific role.",
            "D7": "If my colleagues found AI tools useful, I would be more likely to adopt them too.",
            "D8": "I would be influenced by how my peers or supervisors view the use of AI tools at work.",
        }
    },
    "E": {
        "title": "Perceived Value of AI",
        "questions": {
            "E1": "Overall, the benefits of AI in healthcare outweigh the risks or costs of implementing it.",
            "E2": "AI tools in healthcare will improve the quality and accuracy of decisions in my department.",
            "E3": "AI has the potential to reduce staff burnout by automating repetitive, time-consuming tasks.",
            "E4": "AI will meaningfully improve the experience of patients in our system.",
            "E5": "Overall, I believe AI will have a positive impact on my professional role.",
        }
    },
    "F": {
        "title": "Organisational Culture and Support for AI",
        "questions": {
            "F1": "My organisation's leadership actively ensures the responsible use of AI.",
            "F2": "I feel psychologically safe to raise concerns or questions about AI in my workplace if it is implemented.",
            "F3": "I have received adequate training to use AI tools confidently in my role.",
            "F4": "I am aware of the limitations that come with AI tools.",
            "F5": "I feel capable of critically evaluating and overriding AI recommendations when necessary.",
            "F6": "My workplace has the technical infrastructure needed to support the effective implementation of AI tools.",
            "F7": "I feel that my workplace will take into consideration feedback from its employees during the selection and deployment of AI tools.",
        }
    },
}

# ═══════════════════════════════════════════════════════
# DATABASE SETUP
# ═══════════════════════════════════════════════════════
DB_PATH = os.environ.get("DATABASE_PATH", "booth_data.db")

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
    # AI Acceptance Survey responses
    c.execute("""CREATE TABLE IF NOT EXISTS acceptance_responses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        participant_id TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        age_group TEXT,
        gender TEXT,
        disciplines TEXT,
        years_healthcare TEXT,
        years_role TEXT,
        seniority TEXT,
        ai_frequency TEXT,
        ai_tools TEXT,
        likert_answers TEXT
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
# ROUTES — PARTICIPANT LANDING & ADMIN
# ═══════════════════════════════════════════════════════
@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/admin")
def admin():
    return render_template("admin.html", questions=QUESTIONS, title=APP_TITLE,
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
    for i in range(len(QUESTIONS)):
        entries = get_entries(i)
        texts = [e["text"] for e in entries]
        r[str(i)] = {"words": extract_words(texts) if texts else [],
                      "stats": stats_for(entries), "entries": entries[-10:]}
    ae = []
    for i in range(len(QUESTIONS)):
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
    conn.execute("DELETE FROM acceptance_responses")
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/export")
def api_export():
    data = {}
    for i in range(len(QUESTIONS)):
        data[QUESTIONS[i]] = get_entries(i)
    data["turing_test"] = get_turing_stats()
    data["acceptance_survey"] = api_acceptance_stats().get_json()
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
# ROUTES — PARTICIPANT SURVEYS
# ═══════════════════════════════════════════════════════
@app.route("/survey")
def survey_redirect():
    return redirect(url_for("survey_turing"))


@app.route("/survey/turing")
def survey_turing():
    return render_template("survey_turing.html", title=APP_TITLE,
                           scenarios_json=json.dumps([{"id": s["id"], "patient": s["patient"],
                           "responses": s["responses"]} for s in SCENARIOS]),
                           job_groups=JOB_GROUPS, seniority_levels=SENIORITY_LEVELS,
                           trust_tasks=TRUST_TASKS)


@app.route("/survey/sentiment")
def survey_sentiment():
    return render_template("survey_sentiment.html", questions=QUESTIONS)


@app.route("/survey/acceptance")
def survey_acceptance():
    return render_template("survey_acceptance.html", part_a=ACCEPTANCE_PART_A)


@app.route("/qr")
def qr_code():
    import qrcode
    host = request.host_url.rstrip("/")
    url = f"{host}/survey/turing"
    img = qrcode.make(url, box_size=10, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png", download_name="survey_qr.png")


# ═══════════════════════════════════════════════════════
# ROUTES — AI ACCEPTANCE SURVEY
# ═══════════════════════════════════════════════════════
@app.route("/api/acceptance/submit", methods=["POST"])
def api_acceptance_submit():
    d = request.json or {}
    part_a = d.get("part_a", {})
    likert = d.get("likert_answers", {})

    # Validate required Part A single-select fields
    required = ["age_group", "gender", "years_healthcare", "years_role", "seniority", "ai_frequency"]
    missing = [f for f in required if not part_a.get(f)]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    participant_id = str(uuid.uuid4())[:8]
    ts = datetime.now().isoformat()

    conn = get_db()
    conn.execute(
        """INSERT INTO acceptance_responses
           (participant_id, timestamp, age_group, gender, disciplines,
            years_healthcare, years_role, seniority, ai_frequency, ai_tools, likert_answers)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            participant_id, ts,
            part_a.get("age_group", ""),
            part_a.get("gender", ""),
            json.dumps(part_a.get("disciplines", [])),
            part_a.get("years_healthcare", ""),
            part_a.get("years_role", ""),
            part_a.get("seniority", ""),
            part_a.get("ai_frequency", ""),
            json.dumps(part_a.get("ai_tools", [])),
            json.dumps(likert),
        )
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "participant_id": participant_id})


@app.route("/api/acceptance/stats")
def api_acceptance_stats():
    conn = get_db()
    rows = conn.execute("SELECT * FROM acceptance_responses ORDER BY id").fetchall()
    conn.close()

    total = len(rows)
    if total == 0:
        return jsonify({
            "total_respondents": 0,
            "part_a": {},
            "likert_averages": {},
        })

    # Part A — frequency distributions for each categorical field
    part_a_fields = ["age_group", "gender", "disciplines", "years_healthcare",
                     "years_role", "seniority", "ai_frequency", "ai_tools"]
    part_a_stats = {}
    for field in part_a_fields:
        counts = {}
        for row in rows:
            val = row[field] or ""
            # disciplines and ai_tools are JSON lists
            if field in ("disciplines", "ai_tools"):
                items = json.loads(val) if val else []
                for item in items:
                    counts[item] = counts.get(item, 0) + 1
            else:
                counts[val] = counts.get(val, 0) + 1
        part_a_stats[field] = counts

    # Likert — average score per question key
    sums = {}
    counts_l = {}
    for row in rows:
        answers = json.loads(row["likert_answers"]) if row["likert_answers"] else {}
        for key, val in answers.items():
            try:
                v = int(val)
                sums[key] = sums.get(key, 0) + v
                counts_l[key] = counts_l.get(key, 0) + 1
            except (ValueError, TypeError):
                pass

    likert_averages = {}
    for part_key, part_data in ACCEPTANCE_LIKERT.items():
        part_avgs = {}
        for q_key, q_text in part_data["questions"].items():
            n = counts_l.get(q_key, 0)
            avg = round(sums.get(q_key, 0) / n, 2) if n > 0 else None
            part_avgs[q_key] = {"question": q_text, "avg": avg, "n": n}
        likert_averages[part_key] = {
            "title": part_data["title"],
            "questions": part_avgs,
        }

    return jsonify({
        "total_respondents": total,
        "part_a": part_a_stats,
        "likert_averages": likert_averages,
    })


if __name__ == "__main__":
    print("=" * 60)
    print(f"  {APP_TITLE}  (v4 — with Turing Test)")
    print("=" * 60)
    print(f"  Landing page:  http://localhost:5001/")
    print(f"  Admin:         http://localhost:5001/admin")
    print(f"  Survey/Turing: http://localhost:5001/survey/turing")
    print(f"  QR Code image: http://localhost:5001/qr")
    print(f"  Questions:     {len(QUESTIONS)}")
    print(f"  Scenarios:     {len(SCENARIOS)}")
    print(f"  Database:      {DB_PATH} (SQLite, persists)")
    print("=" * 60)
    port = int(os.environ.get("PORT", 5001))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
