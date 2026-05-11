import streamlit as st
from memory.session import (
    init_session, get_profile, save_profile,
    add_message, get_history, reset_chat, increment_session_count,
)
from memory.profile import UserProfile
from core.prompt_builder import build_system_prompt, PERSONA_LABELS
from core.gemini_client import generate_response

st.set_page_config(page_title="GrowthMentor", page_icon="🎯", layout="centered")

init_session()
profile = get_profile()

PERSONA_CONFIG = {
    "klopp": {
        "icon": "⚽",
        "greeting": lambda name: (
            f"YESSS! {name}, welcome! I am SO excited to be your mentor today! "
            f"Together we're going to learn incredible things — I can feel it! "
            f"So tell me — what do you want to tackle today?"
        ),
    },
    "guardiola": {
        "icon": "📋",
        "greeting": lambda name: (
            f"Welcome, {name}. Let's get straight to work. "
            f"Tell me — what exactly do you want to understand today, "
            f"and what's your current level with it?"
        ),
    },
    "mourinho": {
        "icon": "🏆",
        "greeting": lambda name: (
            f"Alright {name}, let's not waste time. "
            f"What are we working on? And before you answer — "
            f"I want to know what you already tried."
        ),
    },
}


def render_onboarding() -> None:
    st.title("🎯 GrowthMentor")
    st.caption("Your personal AI learning coach — pick your mentor and start growing.")
    st.divider()

    step = st.session_state.get("onboarding_step", 1)

    if step == 1:
        st.subheader("Step 1 of 2 — Tell us about yourself")
        name = st.text_input("What's your name?", placeholder="e.g. Alex", key="ob_name")
        goal = st.text_input(
            "What do you want to learn?",
            placeholder="e.g. Python for data science, Public speaking, ML basics",
            key="ob_goal",
        )
        if st.button("Continue →", disabled=not (name.strip() and goal.strip()), key="ob_continue"):
            profile.name = name.strip()
            profile.learning_goal = goal.strip()
            # persona stays "" so is_complete() stays False → step 2 renders next
            save_profile(profile)
            st.session_state.onboarding_step = 2
            st.rerun()

    elif step == 2:
        st.subheader("Step 2 of 2 — Choose your mentor")
        st.caption("Your coaching style. You can switch anytime from the sidebar.")
        st.write("")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("#### ⚽ Klopp")
            st.caption("**Fun & Inspiring**")
            st.write("High energy. Celebrates every win. Relatable analogies. Best for beginners or anyone needing motivation.")
            if st.button("Choose Klopp", use_container_width=True, key="pick_klopp"):
                _finish_onboarding("klopp")

        with col2:
            st.markdown("#### 📋 Guardiola")
            st.caption("**Serious & Technical ⭐**")
            st.write("Precise and rigorous. Demands real understanding. Best for detail-oriented learners who want depth.")
            if st.button("Choose Guardiola", use_container_width=True, key="pick_guardiola"):
                _finish_onboarding("guardiola")

        with col3:
            st.markdown("#### 🏆 Mourinho")
            st.caption("**Hard-Boiled & Empowering**")
            st.write("Blunt, results-focused, no excuses. Best for people who respond well to being challenged.")
            if st.button("Choose Mourinho", use_container_width=True, key="pick_mourinho"):
                _finish_onboarding("mourinho")


def _finish_onboarding(persona: str) -> None:
    profile.persona = persona
    save_profile(profile)
    increment_session_count()
    cfg = PERSONA_CONFIG[persona]
    add_message("assistant", cfg["greeting"](profile.name))
    st.rerun()


def render_sidebar() -> None:
    with st.sidebar:
        cfg = PERSONA_CONFIG[profile.persona]
        st.markdown(f"### {cfg['icon']} GrowthMentor")
        st.caption(f"Mentor: **{PERSONA_LABELS[profile.persona]}**")
        st.divider()

        st.markdown(f"**Learner:** {profile.name}")
        st.markdown(f"**Goal:** {profile.learning_goal}")
        if profile.current_topic:
            st.markdown(f"**Current topic:** {profile.current_topic}")
        st.markdown(f"**Sessions:** {profile.session_count}")

        if profile.topics_covered:
            st.divider()
            st.markdown("**Topics covered:**")
            for topic in profile.topics_covered:
                score = profile.confidence.get(topic, 0)
                bar = "█" * score + "░" * (5 - score)
                st.caption(f"{topic}  `{bar}` {score}/5")

        st.divider()

        with st.expander("ℹ️ Usage limits (free tier)", expanded=False):
            st.caption(
                "**gemini-2.5-flash**\n"
                "- 5 requests / minute (RPM)\n"
                "- 20 requests / day (RPD)\n"
                "- 250K input tokens / min\n"
                "- Knowledge cutoff: Jan 2025\n"
                "- Web search grounding: enabled"
            )

        st.divider()
        st.markdown("**Switch mentor:**")
        options = ["klopp", "guardiola", "mourinho"]
        new_persona = st.radio(
            "mentor",
            options=options,
            format_func=lambda k: PERSONA_LABELS[k],
            index=options.index(profile.persona),
            label_visibility="collapsed",
            key="sidebar_persona",
        )
        if new_persona != profile.persona:
            profile.persona = new_persona
            save_profile(profile)
            cfg = PERSONA_CONFIG[new_persona]
            add_message("assistant", f"{cfg['icon']} Switched to **{PERSONA_LABELS[new_persona]}**. Your progress is preserved.")
            st.rerun()

        st.divider()
        if st.button("🗑️ Clear chat", use_container_width=True):
            reset_chat()
            st.rerun()
        if st.button("🔄 Reset all (new learner)", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()


def render_chat() -> None:
    cfg = PERSONA_CONFIG[profile.persona]
    st.title(f"{cfg['icon']} GrowthMentor")
    st.caption(f"Mentor: **{PERSONA_LABELS[profile.persona]}** · Goal: *{profile.learning_goal}*")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_input = st.chat_input("Ask your mentor anything about your learning goal...")

    if user_input:
        user_input = user_input.strip()
        if len(user_input) < 2:
            st.warning("Please enter a longer message.")
            return
        if len(user_input) > 1000:
            st.warning("Please keep your message under 1000 characters.")
            return

        with st.chat_message("user"):
            st.markdown(user_input)
        add_message("user", user_input)

        system_prompt = build_system_prompt(profile)
        history = get_history()[:-1]

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = generate_response(
                    user_message=user_input,
                    system_prompt=system_prompt,
                    history=history,
                    use_search=True,
                )
            st.markdown(response)
        add_message("assistant", response)


# ── Router ────────────────────────────────────────────────────────────────────
# is_complete() = bool(name AND learning_goal AND persona)
# persona="" until step 2 → onboarding always shows until all 3 fields are set
if not profile.is_complete():
    render_onboarding()
else:
    render_sidebar()
    render_chat()
