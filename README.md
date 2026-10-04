# CaseMate

An AI Socratic coach for MBA case studies (AI for Managers end-term project, Use Case 16: Case-study coach for MBA courses).

Paste a case, choose SWOT or Porter's Five Forces, answer three questions grounded in the case, and get rubric-based feedback. Rule-based checks verify every AI quote against the case and measure how much case evidence each answer uses.

| File | Purpose |
|---|---|
| `app.py` | Streamlit interface |
| `checks.py` | Rule-based validation, fact extraction, quote verification, evidence scoring |
| `coach.py` | Gemini prompts, rubric and fallback question bank |
| `cases/` | Two fictional sample cases |

The Gemini key is read from Streamlit secrets (`GEMINI_API_KEY`). `GEMINI_MODEL` is optional.
