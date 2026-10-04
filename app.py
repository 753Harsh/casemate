"""
CaseMate - an AI Socratic coach for MBA case studies (Streamlit app).
Gemini key: GEMINI_API_KEY in Streamlit secrets (never in this file).
"""

import json
import os
from datetime import datetime
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

import checks
from coach import DEFAULT_MODEL, FALLBACK_QUESTIONS, RUBRIC, AIUnavailable, give_feedback, make_questions

CASES = {"Chai Junction (tea kiosk chain)": "chai_junction.txt", "VoltRide (EV scooters)": "voltride.txt"}
CASE_DIR = Path(__file__).parent / "cases"

st.set_page_config(page_title="CaseMate", page_icon="🎓", layout="wide")


def setting(name, default=""):
    try:
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass
    return os.environ.get(name, default)


API_KEY = setting("GEMINI_API_KEY")
MODEL = setting("GEMINI_MODEL", DEFAULT_MODEL)
ss = st.session_state
for k, v in {"case": "", "questions": None, "q_source": None, "feedback": None, "fb_error": None}.items():
    ss.setdefault(k, v)


@st.cache_data(show_spinner=False, ttl=3600)
def cached_questions(case, framework, level, facts, model):
    return make_questions(case, framework, level, list(facts), API_KEY, model).model_dump()


@st.cache_data(show_spinner=False, ttl=3600)
def cached_feedback(case, framework, qs_json, answers, rule_json, model):
    return give_feedback(case, framework, json.loads(qs_json), list(answers), json.loads(rule_json), API_KEY, model).model_dump()


def reset():
    for k in ("questions", "q_source", "feedback", "fb_error"):
        ss[k] = None
    for k in list(ss.keys()):
        if str(k).startswith("ans_"):
            del ss[k]


# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.markdown("## 🎓 CaseMate")
    st.caption("Your Socratic coach for MBA case studies")
    framework = st.radio("Framework", list(checks.FRAMEWORKS), on_change=reset)
    level = st.select_slider("Difficulty", ["Foundation", "Intermediate", "Advanced"], value="Intermediate", on_change=reset)
    st.divider()
    offline = st.toggle("Simulate AI outage", help="Test mode: blocks Gemini to show the app still works.")
    if offline:
        st.warning("AI outage simulated. Using the built-in question bank.")
    elif API_KEY:
        st.success(f"Gemini connected · `{MODEL}`")
    else:
        st.info("No Gemini key found. Using the built-in question bank.")
    st.divider()
    st.caption("CaseMate asks questions and gives feedback. It will not write your answers. "
               "Scores are AI judgements against a fixed rubric and can be wrong.")
    st.caption("🔒 Privacy: the case and your answers are sent to Google's Gemini API when AI is on. "
               "Nothing is stored by this app. Do not paste confidential cases.")

# ------------------------------------------------------------------ step 1: case
st.title("CaseMate")
st.markdown("Paste a business case, get three Socratic questions grounded in the case, answer them, "
            "and receive rubric-based feedback.")

st.subheader("① Choose a case")
src = st.radio("Case source", ["Sample case", "Paste my own", "Upload .txt"], horizontal=True, label_visibility="collapsed")
if src == "Sample case":
    pick = st.selectbox("Sample case", list(CASES))
    text = (CASE_DIR / CASES[pick]).read_text(encoding="utf-8")
elif src == "Paste my own":
    text = st.text_area("Case text", height=220, placeholder="Paste the case here (150 to 5,000 words)")
else:
    up = st.file_uploader("Upload a .txt case", type=["txt"])
    text = up.read().decode("utf-8", errors="ignore") if up else ""

with st.expander("Case text and facts found by the app", expanded=False):
    st.write(text[:6000] if text else "No case yet.")
facts = checks.case_facts(text)
c1, c2, c3 = st.columns(3)
c1.metric("Words", len(checks.words(text)))
c2.metric("Reading time", f"{max(1, round(len(checks.words(text)) / 200))} min" if text else "-")
c3.metric("Hard facts found", len(facts))
if facts:
    st.caption("Facts found by rule-based scan: " + " · ".join(facts))

if st.button("Generate questions", type="primary"):
    errs = checks.validate_case(text)
    if errs:
        for e in errs:
            st.error(e)
    else:
        reset()
        ss.case = text
        if offline or not API_KEY:
            ss.questions = [{"framework_element": el, "question": q, "evidence_quote": "", "why_it_matters": ""}
                            for el, q in FALLBACK_QUESTIONS[framework]]
            ss.q_source = "bank"
            ss.summary = None
        else:
            try:
                with st.spinner("CaseMate is reading the case..."):
                    res = cached_questions(text, framework, level, tuple(facts), MODEL)
                ss.questions, ss.q_source = res["questions"][:3], "ai"
                ss.summary = (res["case_summary"], res["key_tension"])
            except AIUnavailable as exc:
                ss.questions = [{"framework_element": el, "question": q, "evidence_quote": "", "why_it_matters": ""}
                                for el, q in FALLBACK_QUESTIONS[framework]]
                ss.q_source = "bank"
                ss.summary = None
                st.warning(f"AI questions are unavailable, so CaseMate is using its built-in question bank. Reason: {exc}")

# ------------------------------------------------------------------ step 2: questions + answers
if ss.questions:
    st.divider()
    st.subheader("② Think it through")
    if ss.q_source == "ai" and ss.get("summary"):
        st.info(f"**Case in brief:** {ss.summary[0]}\n\n**Key tension:** {ss.summary[1]}")
    elif ss.q_source == "bank":
        st.caption("Questions from the built-in bank (AI not used).")
    for i, q in enumerate(ss.questions):
        with st.container(border=True):
            st.markdown(f"**Question {i + 1}** · `{q['framework_element']}`")
            st.markdown(f"#### {q['question']}")
            if q.get("evidence_quote"):
                found = checks.quote_in_case(q["evidence_quote"], ss.case)
                badge = "✅ Quote verified in the case" if found else "⚠️ Quote NOT found in the case. Check it before relying on it."
                st.markdown(f"> {q['evidence_quote']}")
                st.caption(badge + (f" · Why it matters: {q['why_it_matters']}" if q.get("why_it_matters") else ""))
            st.text_area("Your answer", key=f"ans_{i}", height=130, placeholder="Write 25 to 400 words. Use facts from the case.")

    if st.button("Get feedback", type="primary"):
        answers = [ss.get(f"ans_{i}", "") for i in range(len(ss.questions))]
        problems = [(i, checks.validate_answer(a)) for i, a in enumerate(answers)]
        problems = [(i, p) for i, p in problems if p]
        if problems:
            for i, p in problems:
                st.error(f"Answer {i + 1}: {p}")
        else:
            rows = []
            for i, a in enumerate(answers):
                used, phrases = checks.evidence_used(a, ss.case, checks.case_facts(ss.case, 40))
                cover = checks.framework_coverage(a, framework)
                rows.append({"Answer": i + 1, "Words": len(checks.words(a)), "Case facts used": len(used),
                             "Phrases from case": phrases, "Evidence": checks.evidence_level(len(used), phrases),
                             "Framework elements mentioned": ", ".join(cover) or "none",
                             "Integrity": "Flagged" if checks.integrity_hits(a) else "OK"})
            ss.rule_rows = rows
            ss.answers = answers
            ss.feedback, ss.fb_error = None, None
            if offline or not API_KEY:
                ss.fb_error = "AI feedback is unavailable right now. The rule-based evidence checks below still work."
            else:
                try:
                    with st.spinner("CaseMate is reviewing your answers..."):
                        ss.feedback = cached_feedback(ss.case, framework, json.dumps(ss.questions), tuple(answers),
                                                      json.dumps(rows), MODEL)
                except AIUnavailable as exc:
                    ss.fb_error = f"AI feedback is unavailable right now. The rule-based checks below still work. Reason: {exc}"

# ------------------------------------------------------------------ step 3: feedback
if ss.get("rule_rows") and ss.questions:
    st.divider()
    st.subheader("③ Feedback")
    fb = ss.feedback
    rule_flag = any(r.get("Integrity") == "Flagged" for r in ss.rule_rows)
    ai_flag = bool(fb and fb["integrity_flag"])
    if rule_flag or ai_flag:
        who = " and ".join(x for x, f in (("the AI", ai_flag), ("the rule check", rule_flag)) if f)
        st.error(f"🚩 Integrity flag (raised by {who}): an answer asks CaseMate to write the answer or change its rules. "
                 "CaseMate will only coach.")
    if ss.fb_error:
        st.warning(ss.fb_error)
    if fb:
        df = pd.DataFrame(fb["rubric"])
        df["score"] = df["score"].clip(1, 5)
        total = int(df["score"].sum())
        left, right = st.columns([1, 2])
        with left:
            st.metric("Rubric score", f"{total} / {5 * len(df)}")
            chart = alt.Chart(df).mark_bar(cornerRadiusEnd=4, color="#8B1E3F").encode(
                x=alt.X("score:Q", scale=alt.Scale(domain=[0, 5]), title="Score (1-5)"),
                y=alt.Y("criterion:N", sort=None, title=None), tooltip=["criterion", "score"])
            st.altair_chart(chart.properties(height=190), width="stretch")
        with right:
            st.dataframe(df.rename(columns={"criterion": "Criterion", "score": "Score", "reason": "Why"}),
                         hide_index=True, width="stretch")
        a, b = st.columns(2)
        with a:
            st.markdown("**What you did well**")
            for s in fb["strengths"]:
                st.markdown(f"- {s}")
        with b:
            st.markdown("**How to improve**")
            for s in fb["improvements"]:
                st.markdown(f"- {s}")
        st.info(f"**Think further:** {fb['follow_up_question']}")
        ev_score = next((r["score"] for r in fb["rubric"] if "evidence" in r["criterion"].lower()), None)
        if ev_score and ev_score >= 4 and all(r["Evidence"] == "None" for r in ss.rule_rows):
            st.warning("⚖️ Cross-check: the AI rated your use of evidence highly, but the rule-based scan found no case "
                       "facts or phrases in your answers. Treat that score with caution.")
        st.caption("AI-generated feedback. It can be wrong. Use it to improve your thinking, not as a final grade.")

    st.markdown("**Rule-based evidence check** (independent of the AI)")
    st.dataframe(pd.DataFrame(ss.rule_rows), hide_index=True, width="stretch")

    # export
    lines = [f"CaseMate session report - {datetime.now():%d %b %Y %H:%M}", f"Framework: {framework} | Level: {level}", ""]
    for i, q in enumerate(ss.questions):
        lines += [f"Q{i + 1} [{q['framework_element']}]: {q['question']}", f"Answer: {ss.answers[i]}", ""]
    if fb:
        lines += ["Rubric:"] + [f"- {r['criterion']}: {r['score']}/5 - {r['reason']}" for r in fb["rubric"]]
        lines += ["", "Improve:"] + [f"- {s}" for s in fb["improvements"]] + ["", f"Think further: {fb['follow_up_question']}"]
    st.download_button("⬇️ Download session report (.txt)", "\n".join(lines), "casemate_session.txt", type="primary")

st.divider()
with st.expander("How CaseMate works and its limits"):
    st.markdown("**Rubric used for feedback (each 1-5):**")
    st.dataframe(pd.DataFrame(RUBRIC, columns=["Criterion", "What a 5 looks like"]), hide_index=True, width="stretch")
    st.markdown("""
- **Rules (no AI):** check the input, find hard facts in the case, verify that every AI quote really exists in the case,
  and measure how much case evidence each answer uses.
- **Gemini:** writes the Socratic questions and the rubric feedback. It is told never to write answers.
- **Limits:** AI scores are judgements, not marks. CaseMate only knows the case text it is given, and can misread it.
""")
