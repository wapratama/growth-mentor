# GrowthMentor 🎯

A personal AI learning coach built with Gemini 2.5 Flash and Streamlit.  
Choose your mentor persona, define your learning goal, and get coached through any subject, with memory that persists across your session.

---

## Features

- **3 mentor personas** — Klopp (fun), Guardiola (technical), Mourinho (tough love)
- **Conversational memory** — the mentor knows your name, goal, topics covered, and confidence levels
- **Google Search Grounding** — Gemini searches the web automatically for time-sensitive topics
- **Streamlit UI** — runs in any browser, no frontend code required

---

## Project structure

```
growthmentor/
├── app.py                  # Streamlit entry point — UI and routing
├── requirements.txt        # Dependencies
├── .env.example            # API key template (safe to commit)
├── .env                    # Your real key — NEVER commit this
├── .gitignore
│
├── core/
│   ├── gemini_client.py    # Gemini API connection + generate_response()
│   └── prompt_builder.py   # Persona prompts + build_system_prompt()
│
└── memory/
    ├── profile.py          # UserProfile Pydantic model
    └── session.py          # st.session_state helpers
```

---