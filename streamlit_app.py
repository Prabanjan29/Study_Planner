import streamlit as st
from groq import Groq
import json
from datetime import date, timedelta

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Auto Study Planner",
    page_icon="📚",
    layout="centered"
)

# ── Styling ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main { padding: 1rem 1rem 3rem; }
    h1 { font-size: 2rem !important; }
    .stTextArea textarea { font-size: 14px; }
    .day-card {
        background: #f8f7ff;
        border-left: 4px solid #7c6ff7;
        border-radius: 8px;
        padding: 12px 16px;
        margin-bottom: 10px;
    }
    .badge {
        background: #7c6ff7;
        color: white;
        padding: 2px 10px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
    }
    .powered {
        font-size: 12px;
        color: #888;
        text-align: center;
        margin-top: -10px;
        margin-bottom: 16px;
    }
</style>
""", unsafe_allow_html=True)

# ── Groq client setup ─────────────────────────────────────────────────────────
try:
    api_key = st.secrets["GROQ_API_KEY"]
    client = Groq(api_key=api_key)
except Exception:
    st.error("⚠️ Add `GROQ_API_KEY` to `.streamlit/secrets.toml`")
    st.stop()

MODEL = "llama-3.3-70b-versatile"

# ── Helper ────────────────────────────────────────────────────────────────────
def days_until(exam_date: date) -> int:
    return (exam_date - date.today()).days

def call_groq(prompt: str) -> str:
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a smart academic study planner AI. "
                    "Always respond with ONLY valid JSON — no markdown fences, "
                    "no extra text, no preamble."
                )
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.4,
        max_tokens=2000,
    )
    return response.choices[0].message.content.strip()

def build_prompt(syllabus, subject, days, daily_hours, difficulty):
    return f"""Generate a structured JSON study plan for this student:

Subject: {subject}
Syllabus: {syllabus}
Days until exam: {days}
Daily study hours: {daily_hours}
Difficulty: {difficulty}

Return ONLY this exact JSON structure:
{{
  "totalTopics": <number>,
  "recommendedDailyHours": <number>,
  "studyPlan": [
    {{
      "day": 1,
      "date": "<short date like Mon, 28 Apr>",
      "topics": ["topic1", "topic2"],
      "hoursRequired": 2
    }}
  ],
  "flashcards": [
    {{ "question": "What is...?", "answer": "It is..." }}
  ],
  "mockTest": [
    {{
      "question": "Which of the following...?",
      "options": ["A) ...", "B) ...", "C) ...", "D) ..."],
      "correct": 0
    }}
  ]
}}

Rules:
- studyPlan: show max {min(days, 14)} days, distribute all topics evenly
- flashcards: exactly 6 flashcards covering key concepts
- mockTest: exactly 5 MCQs, correct = 0-based index of the right answer
- Keep topic strings concise (max 8 words each)
- Return ONLY the JSON, absolutely nothing else"""

# ── UI ────────────────────────────────────────────────────────────────────────
st.title("📚 Auto Study Planner")
st.markdown(
    '<p class="powered">⚡ Powered by Groq · llama-3.3-70b-versatile (ultra-fast inference)</p>',
    unsafe_allow_html=True
)
st.caption("Paste your syllabus → get a revision plan, flashcards & mock test")

with st.form("planner_form"):
    syllabus = st.text_area(
        "Syllabus / Topics",
        placeholder=(
            "Unit 1: Machine Learning basics, regression, classification\n"
            "Unit 2: Neural Networks, backpropagation, CNNs\n"
            "Unit 3: NLP, transformers, BERT\n"
            "Unit 4: Reinforcement Learning, Q-learning\n..."
        ),
        height=160
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        subject = st.text_input("Subject", placeholder="e.g. Deep Learning")
    with col2:
        exam_date = st.date_input(
            "Exam Date",
            value=date.today() + timedelta(days=14),
            min_value=date.today() + timedelta(days=1)
        )
    with col3:
        daily_hours = st.number_input("Daily Study Hours", min_value=1, max_value=12, value=3)

    difficulty = st.select_slider(
        "Difficulty Level",
        options=["Easy", "Medium", "Hard"],
        value="Medium"
    )

    submitted = st.form_submit_button("🚀 Generate My Study Plan", use_container_width=True)

# ── Generation ────────────────────────────────────────────────────────────────
if submitted:
    if not syllabus.strip():
        st.warning("Please paste your syllabus topics.")
        st.stop()

    days = days_until(exam_date)
    if days < 1:
        st.error("Exam date must be in the future.")
        st.stop()

    with st.spinner("⚡ Groq is generating your plan at lightning speed..."):
        try:
            prompt = build_prompt(
                syllabus.strip(),
                subject or "the subject",
                days,
                daily_hours,
                difficulty
            )
            raw = call_groq(prompt)

            # Strip markdown fences if Groq adds them anyway
            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            raw = raw.strip()

            data = json.loads(raw)

        except json.JSONDecodeError:
            st.error("⚠️ Groq returned unexpected output. Please try again.")
            st.stop()
        except Exception as e:
            st.error(f"Error: {e}")
            st.stop()

    st.success("✅ Plan generated!")

    # ── Stats ─────────────────────────────────────────────────────────────────
    st.markdown("---")
    m1, m2, m3 = st.columns(3)
    m1.metric("📅 Days Left", days)
    m2.metric("📖 Total Topics", data.get("totalTopics", "—"))
    m3.metric("⏱ Rec. Daily Hours", f"{data.get('recommendedDailyHours', daily_hours)}h")

    # ── Tabs ──────────────────────────────────────────────────────────────────
    tab1, tab2, tab3 = st.tabs(["📅 Study Plan", "🃏 Flashcards", "✏️ Mock Test"])

    # ── Study Plan ────────────────────────────────────────────────────────────
    with tab1:
        st.subheader("Your Revision Schedule")
        plan = data.get("studyPlan", [])
        if not plan:
            st.info("No plan generated.")
        for d in plan:
            topics_li = "".join(
                f"<li>› {t}</li>" for t in d.get("topics", [])
            )
            st.markdown(f"""
<div class="day-card">
  <b>Day {d['day']} — {d.get('date', '')}</b>
  &nbsp;<span class="badge">{d.get('hoursRequired', '?')}h</span>
  <ul style="margin:8px 0 0 0; padding-left:16px; font-size:14px; line-height:1.8;">
    {topics_li}
  </ul>
</div>
""", unsafe_allow_html=True)

    # ── Flashcards ────────────────────────────────────────────────────────────
    with tab2:
        st.subheader("Key Concept Flashcards")
        cards = data.get("flashcards", [])
        if not cards:
            st.info("No flashcards generated.")
        for card in cards:
            with st.expander(f"🃏 {card.get('question', 'Question')}", expanded=False):
                st.success(card.get("answer", "—"))

    # ── Mock Test ─────────────────────────────────────────────────────────────
    with tab3:
        st.subheader("Mock Test — 5 Questions")
        questions = data.get("mockTest", [])
        if not questions:
            st.info("No mock test generated.")
        else:
            answers = {}
            with st.form("mock_test_form"):
                for i, q in enumerate(questions):
                    st.markdown(f"**Q{i+1}. {q.get('question', '')}**")
                    options = q.get("options", [])
                    choice = st.radio(
                        label=f"q{i}",
                        options=range(len(options)),
                        format_func=lambda x, opts=options: opts[x],
                        key=f"q_{i}",
                        label_visibility="collapsed"
                    )
                    answers[i] = {
                        "selected": choice,
                        "correct": q.get("correct", 0)
                    }
                    st.markdown("")

                check = st.form_submit_button("✅ Check My Answers", use_container_width=True)

            if check:
                score = 0
                for i, a in answers.items():
                    if a["selected"] == a["correct"]:
                        st.success(f"Q{i+1}: Correct! ✅")
                        score += 1
                    else:
                        correct_text = questions[i]["options"][a["correct"]]
                        st.error(f"Q{i+1}: Wrong ❌ — Correct: **{correct_text}**")

                st.markdown("---")
                pct = int((score / len(answers)) * 100)
                if pct == 100:
                    st.balloons()
                    st.success(f"🎉 Perfect score! {score}/{len(answers)} ({pct}%)")
                elif pct >= 60:
                    st.info(f"📊 Score: {score}/{len(answers)} ({pct}%) — Keep revising!")
                else:
                    st.warning(f"📊 Score: {score}/{len(answers)} ({pct}%) — More practice needed.")
