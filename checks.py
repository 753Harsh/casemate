"""
CaseMate - rule-based checks (no AI).

These checks run before and after Gemini. They validate the input, pull the
hard facts out of the case, and independently test whether the student's
answers actually use case evidence. The AI never overrides these numbers.
"""

import re

MIN_CASE_WORDS, MAX_CASE_WORDS = 150, 5000
MIN_ANSWER_WORDS, MAX_ANSWER_WORDS = 25, 400

FRAMEWORKS = {
    "SWOT": {
        "Strengths": ["strength", "advantage", "strong", "edge"],
        "Weaknesses": ["weakness", "weak", "limitation", "problem"],
        "Opportunities": ["opportunit", "growth", "untapped", "expand"],
        "Threats": ["threat", "risk", "competit", "regulat"],
    },
    "Porter's Five Forces": {
        "Rivalry": ["rival", "competit", "price war"],
        "New entrants": ["entrant", "entry", "barrier"],
        "Substitutes": ["substitut", "alternative"],
        "Supplier power": ["supplier", "input cost", "vendor"],
        "Buyer power": ["buyer", "customer power", "bargaining", "switch"],
    },
}

FACT_RE = re.compile(
    r"(?:₹|Rs\.?|INR|\$)\s?\d[\d,]*(?:\.\d+)?\s?(?:crore|lakh|million|billion|cr|k)?"
    r"|\d[\d,]*(?:\.\d+)?\s?(?:%|percent|crore|lakh|million|billion)"
    r"|\b(?:19|20)\d{2}\b",
    re.IGNORECASE,
)

def words(text):
    return re.findall(r"[A-Za-z0-9₹%']+", text or "")

def norm(text):
    return re.sub(r"\s+", " ", re.sub(r"[\"'“”‘’`]", "", (text or "").lower())).strip()

def validate_case(text):
    """Returns a list of problems; empty means the case can be used."""
    text = (text or "").strip()
    n = len(words(text))
    errors = []
    if n == 0:
        errors.append("Please paste a case or choose a sample case.")
    elif n < MIN_CASE_WORDS:
        errors.append(f"The case is too short ({n} words). Paste at least {MIN_CASE_WORDS} words so the questions can be grounded in it.")
    elif n > MAX_CASE_WORDS:
        errors.append(f"The case is too long ({n} words). Please keep it under {MAX_CASE_WORDS} words.")
    letters = sum(c.isalpha() for c in text)
    if text and letters / max(len(text), 1) < 0.55:
        errors.append("This does not look like a written case (too few letters). Please paste the case text.")
    return errors

def case_facts(text, limit=15):
    seen, out = set(), []
    for m in FACT_RE.finditer(text or ""):
        f = m.group(0).strip()
        if f.lower() not in seen:
            seen.add(f.lower()); out.append(f)
        if len(out) >= limit:
            break
    return out

def validate_answer(ans):
    n = len(words(ans))
    if n == 0:
        return "Not answered yet."
    if n < MIN_ANSWER_WORDS:
        return f"Too short to assess ({n} words). Write at least {MIN_ANSWER_WORDS} words."
    if n > MAX_ANSWER_WORDS:
        return f"Too long ({n} words). Keep it under {MAX_ANSWER_WORDS} words."
    return None

def quote_in_case(quote, case_text):
    q = norm(quote).rstrip(".")
    return len(q.split()) >= 4 and q in norm(case_text)

def evidence_used(answer, case_text, facts):
    """Counts case facts and 6-word phrases from the case that appear in the answer."""
    a = norm(answer)
    facts_used = [f for f in facts if norm(f) in a]
    cw, aw = norm(case_text).split(), a.split()
    case_grams = {" ".join(cw[i:i + 6]) for i in range(len(cw) - 5)}
    phrases = sum(1 for i in range(len(aw) - 5) if " ".join(aw[i:i + 6]) in case_grams)
    return facts_used, phrases

def framework_coverage(text, framework):
    t = (text or "").lower()
    return [el for el, kws in FRAMEWORKS[framework].items() if any(k in t for k in kws)]

def evidence_level(n_facts, n_phrases):
    total = n_facts + min(n_phrases, 3)
    return "Strong" if total >= 3 else "Some" if total >= 1 else "None"
