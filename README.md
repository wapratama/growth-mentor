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

## Project Structure

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
│   ├── quiz_engine.py      # Quiz generation and scoring logic
│   ├── safety_filter.py    # Moderation and content filtering
│   └── prompt_builder.py   # Persona prompts + build_system_prompt()
│
└── memory/
    ├── profile.py          # UserProfile Pydantic model
    ├── session.py          # st.session_state helpers
    └── updater.py          # Memory Updater
```

---
## Reproducibility

### Clone Repository
```bash
git clone https://github.com/wapratama/growth-mentor.git
cd growth-mentor

# Set API Key
cp .env.example .env
# edit .env with your API Key from https://aistudio.google.com/app/apikey
```

### Local Setup
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
source venv/Scripts/activate

# Install dependencies
pip install -r requirements.txt
```

### Local Run
```bash
streamlit run app.py
```

### Deploying to Streamlit Community Cloud (free)

1. Push your repo to GitHub (make sure `.env` is in `.gitignore`)
2. Go to https://share.streamlit.io → New app → select your repo
3. In **Advanced settings → Secrets**, add:
   ```toml
   GEMINI_API_KEY = "your_key_here"
   ```
4. Click **Deploy**

---

## Tech Stack
- Python
- Streamlit
- Gemini API
- Google Search API

---

## Author
- Wisnu Anugrah Pratama
- Email: wisnuanugrahpratama@gmail.com
- GitHub: https://github.com/wapratama
- LinkedIn: [Wisnu Anugrah Pratama](https://www.linkedin.com/in/wisnuanugrahpratama/)

---