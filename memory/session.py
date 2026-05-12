import streamlit as st
from memory.profile import UserProfile


def init_session() -> None:
    """Initialize all session state keys if they don't exist yet."""
    if "profile" not in st.session_state:
        st.session_state.profile = UserProfile()
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "onboarding_step" not in st.session_state:
        st.session_state.onboarding_step = 1
    if "message_count" not in st.session_state:
        st.session_state.message_count = 0  # tracks total user messages for Gemini throttle


def get_profile() -> UserProfile:
    return st.session_state.profile


def save_profile(profile: UserProfile) -> None:
    st.session_state.profile = profile


def add_message(role: str, content: str) -> None:
    """Append a message to the chat history. role is 'user' or 'assistant'."""
    st.session_state.messages.append({"role": role, "content": content})


def get_history() -> list[dict]:
    """Return the full chat history, capped at the last 20 messages to control token usage."""
    return st.session_state.messages[-20:]


def reset_chat() -> None:
    """Clear chat history but keep the user profile intact."""
    st.session_state.messages = []
    st.session_state.message_count = 0


def increment_session_count() -> None:
    st.session_state.profile.session_count += 1


def get_message_count() -> int:
    return st.session_state.get("message_count", 0)


def increment_message_count() -> int:
    """Increment total user message count and return the new value."""
    st.session_state.message_count = st.session_state.get("message_count", 0) + 1
    return st.session_state.message_count
