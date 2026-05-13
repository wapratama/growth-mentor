import html as html_lib
import streamlit as st
from memory.session import (
    init_session, get_profile, save_profile,
    add_message, get_history, reset_chat,
    increment_session_count, increment_message_count,
)
from memory.profile import UserProfile
from memory.updater import update_memory, GEMINI_UPDATE_EVERY_N
from core.prompt_builder import build_system_prompt, PERSONA_LABELS
from core.gemini_client import generate_response
from core.safety_filter import run_safety_check
from core.quiz_engine import (
    generate_quiz, score_quiz, confidence_from_score,
    build_result_message, is_quiz_request, Quiz,
)

st.set_page_config(page_title="GrowthMentor", page_icon="🎯", layout="centered")

init_session()
profile = get_profile()

PERSONA_CONFIG = {
    "klopp":     {"icon": "⚽", "greeting": lambda n: f"YESSS! {n}, welcome! I am SO excited to be your mentor today! Together we're going to learn incredible things — I can feel it! So tell me — what do you want to tackle today?"},
    "guardiola": {"icon": "📋", "greeting": lambda n: f"Welcome, {n}. Let's get straight to work. Tell me — what exactly do you want to understand today, and what's your current level with it?"},
    "mourinho":  {"icon": "🏆", "greeting": lambda n: f"Alright {n}, let's not waste time. What are we working on? And before you answer — I want to know what you already tried."},
}


# ── Chat bubble CSS ───────────────────────────────────────────────────────────
def _inject_chat_css() -> None:
    """
    Inject CSS for an elegant, professional, and engaging two-column chat layout.
    Features:
      - Assistant messages → left-aligned, clean themed bubble with subtle shadow
      - User messages      → right-aligned, dynamic premium blue gradient bubble
      - Avatars            → custom gradients, hover effects, and entrance animations
      - Transitions        → smooth box-shadow and transform animations on hover
    """
    st.markdown("""
<style>
/* ── Main Chat Container Tweaks ── */
[data-testid="stChatMessageContainer"] {
    gap: 1.5rem;
}

/* ── Shared Bubble Styles ── */
[data-testid="stChatMessage"] {
    padding: 0.5rem 0;
}

[data-testid="stChatMessage"] [data-testid="stChatMessageContent"] {
    padding: 16px 22px;
    font-size: 1rem;
    line-height: 1.6;
    box-shadow: 0 4px 15px rgba(0,0,0,0.05);
    transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
}

[data-testid="stChatMessage"] [data-testid="stChatMessageContent"]:hover {
    box-shadow: 0 8px 25px rgba(0,0,0,0.1);
    transform: translateY(-2px);
}

/* ── Avatar Styling ── */
[data-testid="stChatMessageAvatarUser"],
[data-testid="stChatMessageAvatarAssistant"] {
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    border: 2px solid var(--background-color, white);
    border-radius: 50%;
    transition: transform 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    width: 2.5rem;
    height: 2.5rem;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: visible;
}

[data-testid="stChatMessageAvatarUser"]:hover,
[data-testid="stChatMessageAvatarAssistant"]:hover {
    transform: scale(1.15) rotate(5deg);
}

/* ── Assistant bubble: left-aligned ── */
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
    flex-direction: row;
    align-items: flex-end; /* Align to bottom for a modern chat look */
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"])
    [data-testid="stChatMessageContent"] {
    background: var(--secondary-background-color, #f8f9fa);
    color: var(--text-color, #1e293b);
    border-radius: 20px 20px 20px 4px;
    margin-right: 15%;
    border: 1px solid rgba(128, 128, 128, 0.1);
    margin-left: 12px;
}

[data-testid="stChatMessageAvatarAssistant"] {
    background: linear-gradient(135deg, #4b4dab, #946eeb); /* Indigo to Purple */
}
[data-testid="stChatMessageAvatarAssistant"] svg {
    fill: white;
}

/* Assistant links */
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"])
    [data-testid="stChatMessageContent"] a {
    color: #6366f1;
    text-decoration: none;
    font-weight: 600;
    transition: color 0.2s;
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"])
    [data-testid="stChatMessageContent"] a:hover {
    color: #4f46e5;
    text-decoration: underline;
}

/* ── User bubble: right-aligned ── */
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
    flex-direction: row-reverse;
    align-items: flex-end;
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"])
    [data-testid="stChatMessageContent"] {
    background: linear-gradient(135deg, #0ea5e9, #2563eb); /* Premium Blue */
    color: white;
    border-radius: 20px 20px 4px 20px;
    margin-left: 15%;
    border: none;
    margin-right: 12px;
    box-shadow: 0 4px 15px rgba(37, 99, 235, 0.2);
}

[data-testid="stChatMessageAvatarUser"] {
    background: linear-gradient(135deg, #8c9fba, #0f172a); /* Slate gradient */
}
[data-testid="stChatMessageAvatarUser"] svg {
    fill: white;
}

/* Keep user message text white */
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"])
    [data-testid="stChatMessageContent"] p,
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"])
    [data-testid="stChatMessageContent"] a,
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"])
    [data-testid="stChatMessageContent"] li,
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"])
    [data-testid="stChatMessageContent"] code {
    color: white !important;
}

/* Entrance Animation */
@keyframes popIn {
    0% { opacity: 0; transform: scale(0.5); }
    70% { transform: scale(1.1); }
    100% { opacity: 1; transform: scale(1); }
}
[data-testid="stChatMessageAvatarAssistant"],
[data-testid="stChatMessageAvatarUser"] {
    animation: popIn 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards;
}
</style>
""", unsafe_allow_html=True)


def _render_history() -> None:
    """Render all messages in the two-column bubble layout."""
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])


# ── Onboarding ──────────────────────────────────────────────────────────────
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
    add_message("assistant", PERSONA_CONFIG[persona]["greeting"](profile.name))
    st.rerun()


# ── Sidebar ──────────────────────────────────────────────────────────────────
def render_sidebar() -> None:
    with st.sidebar:
        cfg = PERSONA_CONFIG[profile.persona]
        st.markdown(f"### {cfg['icon']} GrowthMentor")
        st.caption(f"Mentor: **{PERSONA_LABELS[profile.persona]}**")
        st.divider()

        st.markdown(f"**Learner:** {profile.name}")
        st.markdown(f"**Goal:** {profile.learning_goal}")
        if profile.current_topic:
            st.markdown(f"**Now:** {profile.current_topic}")
        st.markdown(f"**Sessions:** {profile.session_count}")

        if profile.last_session_summary:
            st.divider()
            st.markdown("**Last summary:**")
            st.caption(profile.last_session_summary)

        if profile.topics_covered:
            st.divider()
            st.markdown("**Topics covered:**")
            for topic in profile.topics_covered:
                score = profile.confidence.get(topic, 0)
                st.caption(
                    f"{topic}  `{'█' * score}{'░' * (5 - score)}`  "
                    f"{profile.display_confidence(topic)}"
                )

        # Quiz progress
        if profile.quizzes_taken > 0:
            st.divider()
            st.markdown("**📊 Quiz progress:**")
            acc = profile.overall_accuracy()
            st.caption(f"Overall accuracy: **{acc}%**")
            st.progress(int(acc) / 100)
            st.caption(
                f"Quizzes taken: **{profile.quizzes_taken}** · "
                f"Questions: **{profile.quiz_correct_answers}**/**{profile.quiz_total_questions}** correct"
            )
            badges = []
            if profile.quizzes_taken >= 1:  badges.append("🥉 First quiz")
            if profile.quizzes_taken >= 5:  badges.append("🥈 5 quizzes")
            if profile.quizzes_taken >= 10: badges.append("🥇 10 quizzes")
            if acc >= 80:                   badges.append("🎯 Sharp shooter")
            if acc == 100 and profile.quizzes_taken >= 3: badges.append("🏆 Perfect run")
            if badges:
                st.caption("  ".join(badges))

        st.divider()
        quiz_label = f"📝 Quiz me on: {profile.current_topic}" if profile.current_topic else "📝 Take a quiz"
        if st.button(quiz_label, use_container_width=True,
                     disabled=st.session_state.get("quiz_active", False),
                     key="sidebar_quiz_btn"):
            _start_quiz()

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
            "mentor", options=options,
            format_func=lambda k: PERSONA_LABELS[k],
            index=options.index(profile.persona),
            label_visibility="collapsed",
            key="sidebar_persona",
        )
        if new_persona != profile.persona:
            profile.persona = new_persona
            save_profile(profile)
            cfg = PERSONA_CONFIG[new_persona]
            add_message("assistant",
                        f"{cfg['icon']} Switched to **{PERSONA_LABELS[new_persona]}**. Your progress is preserved.")
            st.rerun()

        st.divider()
        if st.button("🗑️ Clear chat", use_container_width=True):
            reset_chat()
            st.session_state.pop("quiz_active", None)
            st.session_state.pop("active_quiz", None)
            st.rerun()
        if st.button("🔄 Reset all (new learner)", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()


# ── Quiz helpers ──────────────────────────────────────────────────────────────
def _start_quiz() -> None:
    with st.spinner("Generating your quiz..."):
        quiz = generate_quiz(get_profile())
    if quiz and quiz.questions:
        st.session_state.active_quiz   = quiz
        st.session_state.quiz_answers  = {}
        st.session_state.quiz_submitted = False
        st.session_state.quiz_active   = True
        st.rerun()
    else:
        st.error("Couldn't generate a quiz right now. Please try again in a moment.")


def render_quiz() -> None:
    quiz: Quiz = st.session_state.active_quiz
    cfg = PERSONA_CONFIG[profile.persona]

    st.title(f"{cfg['icon']} Quiz — {quiz.topic}")
    st.caption(
        f"Mentor: **{PERSONA_LABELS[profile.persona]}** · "
        f"{len(quiz.questions)} questions · 1 point each"
    )
    st.divider()

    submitted   = st.session_state.get("quiz_submitted", False)
    user_answers: dict = st.session_state.get("quiz_answers", {})

    for i, q in enumerate(quiz.questions):
        st.markdown(f"**Q{i + 1}. {q.question}**")

        if not submitted:
            selected = st.radio(
                f"q{i}", options=range(4),
                format_func=lambda j, opts=q.options: f"{chr(65+j)}) {opts[j]}",
                index=user_answers.get(i, 0),
                label_visibility="collapsed",
                key=f"quiz_q{i}",
            )
            user_answers[i] = selected
        else:
            for j, opt in enumerate(q.options):
                is_correct = (j == q.correct_index)
                is_chosen  = (user_answers.get(i) == j)
                if is_correct:
                    st.success(f"{chr(65+j)}) {opt} ✓")
                elif is_chosen and not is_correct:
                    st.error(f"{chr(65+j)}) {opt} ✗")
                else:
                    st.write(f"{chr(65+j)}) {opt}")
            st.info(f"💡 {q.explanation}")
        st.write("")

    st.session_state.quiz_answers = user_answers

    if not submitted:
        answered = len(user_answers)
        total_q  = len(quiz.questions)
        if st.button(
            f"Submit answers ({answered}/{total_q} answered)",
            disabled=(answered < total_q),
            key="quiz_submit", type="primary",
        ):
            _submit_quiz(quiz, user_answers)
    else:
        correct, total = quiz.score, quiz.total
        pct = int(correct / total * 100) if total else 0

        st.divider()
        col1, col2, col3 = st.columns(3)
        col1.metric("Score", f"{correct}/{total}")
        col2.metric("Accuracy", f"{pct}%")
        col3.metric("Quizzes taken", profile.quizzes_taken)
        st.markdown(f"> *{build_result_message(quiz, correct, total)}*")

        col_a, col_b = st.columns(2)
        if col_a.button("📝 New quiz", use_container_width=True, key="new_quiz_btn"):
            for k in ("active_quiz", "quiz_answers", "quiz_submitted"):
                st.session_state.pop(k, None)
            st.session_state.quiz_active = False
            _start_quiz()
        if col_b.button("💬 Back to chat", use_container_width=True, key="back_to_chat_btn"):
            for k in ("active_quiz", "quiz_answers", "quiz_submitted"):
                st.session_state.pop(k, None)
            st.session_state.quiz_active = False
            st.rerun()


def _submit_quiz(quiz: Quiz, user_answers: dict) -> None:
    correct, total = score_quiz(quiz, user_answers)
    fresh = get_profile()
    fresh.record_quiz(quiz.topic, correct, total)
    fresh.confidence[quiz.topic] = confidence_from_score(correct, total)
    save_profile(fresh)
    st.session_state.quiz_submitted = True
    st.rerun()


# ── Chat ──────────────────────────────────────────────────────────────────────
def render_chat() -> None:
    cfg = PERSONA_CONFIG[profile.persona]

    # Inject two-column bubble CSS (called once per render, idempotent)
    _inject_chat_css()

    st.title(f"{cfg['icon']} GrowthMentor")
    st.caption(
        f"Mentor: **{PERSONA_LABELS[profile.persona]}** · "
        f"Goal: *{profile.learning_goal}*"
    )

    # Render history with bubble layout
    _render_history()

    user_input = st.chat_input("Ask your mentor, or type 'quiz me' to take a quiz...")

    if user_input:
        # ── Safety check ──────────────────────────────────────────────────
        safety = run_safety_check(user_input)
        if not safety.is_safe:
            st.warning(safety.block_reason)
            return

        clean_input = safety.sanitized_text

        # ── Quiz intent ───────────────────────────────────────────────────
        if is_quiz_request(clean_input):
            with st.chat_message("user"):
                st.markdown(user_input)
            with st.chat_message("assistant"):
                with st.spinner("Generating your quiz..."):
                    quiz = generate_quiz(get_profile())
                if quiz and quiz.questions:
                    st.success(f"Quiz ready! Switching to quiz mode on: **{quiz.topic}**")
                    st.session_state.active_quiz   = quiz
                    st.session_state.quiz_answers  = {}
                    st.session_state.quiz_submitted = False
                    st.session_state.quiz_active   = True
                    st.rerun()
                else:
                    err = "I couldn't generate a quiz right now — please try again in a moment."
                    st.markdown(err)
                    add_message("user", clean_input)
                    add_message("assistant", err)
            return

        # ── Normal chat ───────────────────────────────────────────────────
        with st.chat_message("user"):
            st.markdown(user_input)
        add_message("user", clean_input)

        system_prompt = build_system_prompt(profile)
        history = get_history()[:-1]

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = generate_response(
                    user_message=clean_input,
                    system_prompt=system_prompt,
                    history=history,
                    use_search=True,
                )
            st.markdown(response)

        add_message("assistant", response)

        # ── Memory update ─────────────────────────────────────────────────
        msg_count = increment_message_count()
        with st.spinner("Updating memory..."):
            updated = update_memory(
                profile=get_profile(),
                user_message=clean_input,
                assistant_message=response,
                message_count=msg_count,
            )
        save_profile(updated)

        if msg_count % GEMINI_UPDATE_EVERY_N == 0 and updated.current_topic:
            st.toast(f"📚 Memory updated — current topic: {updated.current_topic}", icon="🧠")


# ── Router ────────────────────────────────────────────────────────────────────
if not profile.is_complete():
    render_onboarding()
elif st.session_state.get("quiz_active", False):
    render_sidebar()
    render_quiz()
else:
    render_sidebar()
    render_chat()
