"""
memory/updater.py — Phase 2: Memory Updater

Strategy: hybrid extraction to protect the 20 RPD free-tier limit.

  Every message  → rule_based_update()   (free, instant)
  Every 3rd msg  → gemini_memory_update() (1 API call, structured JSON)

The Gemini extraction call is intentionally minimal:
  - Only last 2 exchanges sent (not full history)
  - No search grounding
  - max_output_tokens=256
  - JSON-only output
"""

import json
import logging
import re
import os
from google import genai
from google.genai import types
from dotenv import load_dotenv
from memory.profile import UserProfile

load_dotenv()
logger = logging.getLogger(__name__)

# How often to run the full Gemini extraction (every N messages)
GEMINI_UPDATE_EVERY_N = 3

# Extraction model — same model, much smaller call
MODEL_ID = "gemini-2.5-flash"

# ── Extraction prompt ────────────────────────────────────────────────────────
_EXTRACTION_PROMPT = """You are a learning analytics engine. Analyse the conversation excerpt below and extract structured data about the learner's progress.

Learner's overall goal: {goal}
Topics already tracked: {known_topics}

Conversation:
USER: {user_msg}
MENTOR: {assistant_msg}

Reply with ONLY a valid JSON object. No markdown. No explanation. No extra text.
Use exactly this schema:
{{
  "current_topic": "<the specific topic being discussed right now, 2-5 words>",
  "topics_discussed": ["<topic1>", "<topic2>"],
  "confidence_updates": {{"<topic>": <score 1-5>}},
  "session_summary": "<one sentence summary of what the learner worked on and their progress>"
}}

Rules for confidence scores (1-5):
1 = Just introduced, learner seems lost
2 = Familiar but making errors
3 = Understands basics, some gaps
4 = Solid understanding, minor gaps
5 = Mastered, can explain it back clearly

Only include topics and confidence scores that were actually discussed in this exchange.
If confidence cannot be determined, omit the topic from confidence_updates.
"""


# ── Rule-based update (free, every message) ──────────────────────────────────
def rule_based_update(profile: UserProfile, user_message: str) -> UserProfile:
    """
    Fast, free extraction based on string matching.
    Detects topic keywords from the learning goal and user message,
    then appends newly mentioned topics to topics_covered.

    This runs on EVERY message at zero API cost.
    """
    # Tokenise the user message into candidate topic words (2+ chars, no stopwords)
    stopwords = {
        "the", "a", "an", "is", "it", "in", "on", "at", "to", "for",
        "of", "and", "or", "but", "how", "what", "why", "when", "can",
        "do", "does", "me", "my", "i", "you", "we", "help", "about",
        "tell", "explain", "understand", "know", "learn", "want",
    }
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9_\+\#\-]{1,}", user_message.lower())
    candidates = [w for w in words if w not in stopwords and len(w) > 2]

    # Build a normalised set of known topics for dedup
    known_lower = {t.lower() for t in profile.topics_covered}

    # Check if any candidate word matches (or is contained in) the learning goal
    goal_words = set(profile.learning_goal.lower().split())

    for candidate in candidates:
        # Add topic if it overlaps with the goal domain and isn't already tracked
        if candidate not in known_lower and (
            candidate in goal_words
            or any(candidate in gw or gw in candidate for gw in goal_words)
        ):
            # Capitalise nicely before storing
            topic = candidate.capitalize()
            profile.topics_covered.append(topic)
            known_lower.add(candidate)
            logger.debug(f"Rule-based: added topic '{topic}'")

    return profile


# ── Gemini-assisted update (1 API call, every N messages) ────────────────────
def gemini_memory_update(
    profile: UserProfile,
    user_message: str,
    assistant_message: str,
) -> UserProfile:
    """
    Uses a lightweight Gemini call to extract structured memory updates.
    Returns the updated profile. On any failure, returns the profile unchanged.

    Cost: 1 API call. Called every GEMINI_UPDATE_EVERY_N messages only.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.warning("GEMINI_API_KEY not set — skipping Gemini memory update")
        return profile

    prompt = _EXTRACTION_PROMPT.format(
        goal=profile.learning_goal,
        known_topics=", ".join(profile.topics_covered) or "none yet",
        user_msg=user_message[:500],          # cap to protect tokens
        assistant_msg=assistant_message[:800],
    )

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
            config=types.GenerateContentConfig(
                max_output_tokens=256,
                temperature=0.1,   # low temperature = more reliable JSON
            ),
        )

        raw = response.text or ""
        logger.info(f"Memory extraction raw response: {raw[:200]}")

        data = _parse_extraction(raw)
        if data:
            profile = _apply_extraction(profile, data)
        else:
            logger.warning("Memory extraction returned unparseable JSON — skipping update")

    except Exception as e:
        logger.error(f"Gemini memory update failed: {e} — profile unchanged")

    return profile


def _parse_extraction(raw: str) -> dict | None:
    """
    Safely parse the JSON from Gemini's extraction response.
    Strips markdown fences if present. Returns None on failure.
    """
    # Strip markdown code fences (```json ... ```) if Gemini ignores our instructions
    cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()

    # Find the outermost JSON object
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
        logger.warning(f"No JSON object found in extraction: {raw[:100]}")
        return None

    try:
        return json.loads(match.group())
    except json.JSONDecodeError as e:
        logger.warning(f"JSON parse error in extraction: {e}")
        return None


def _apply_extraction(profile: UserProfile, data: dict) -> UserProfile:
    """Apply validated extraction data to the profile."""
    # 1. Update current topic
    current_topic = data.get("current_topic", "").strip()
    if current_topic and len(current_topic) < 60:
        profile.current_topic = current_topic
        logger.info(f"Memory update: current_topic='{current_topic}'")

    # 2. Add newly discovered topics to topics_covered
    known_lower = {t.lower() for t in profile.topics_covered}
    for topic in data.get("topics_discussed", []):
        topic = topic.strip()
        if topic and topic.lower() not in known_lower and len(topic) < 60:
            profile.topics_covered.append(topic)
            known_lower.add(topic.lower())
            logger.info(f"Memory update: added topic '{topic}'")

    # 3. Update confidence scores (clamp to 1–5 range)
    for topic, score in data.get("confidence_updates", {}).items():
        topic = topic.strip()
        if topic and isinstance(score, (int, float)):
            clamped = max(1, min(5, int(score)))
            profile.confidence[topic] = clamped
            logger.info(f"Memory update: confidence['{topic}']={clamped}")

    # 4. Update session summary
    summary = data.get("session_summary", "").strip()
    if summary and len(summary) < 300:
        profile.last_session_summary = summary
        logger.info(f"Memory update: session_summary updated")

    return profile


# ── Main entry point ─────────────────────────────────────────────────────────
def update_memory(
    profile: UserProfile,
    user_message: str,
    assistant_message: str,
    message_count: int,
) -> UserProfile:
    """
    Central dispatcher for memory updates. Call this after every assistant response.

    Args:
        profile:           The current UserProfile to update.
        user_message:      The user's last message.
        assistant_message: The assistant's last response.
        message_count:     Total messages sent so far (used to throttle Gemini calls).

    Returns:
        Updated UserProfile (always safe to use, even if Gemini call fails).
    """
    # Step 1: rule-based (always, free)
    profile = rule_based_update(profile, user_message)

    # Step 2: Gemini-assisted (every N messages)
    if message_count % GEMINI_UPDATE_EVERY_N == 0:
        logger.info(f"Message #{message_count} — running Gemini memory extraction")
        profile = gemini_memory_update(profile, user_message, assistant_message)
    else:
        logger.debug(f"Message #{message_count} — rule-based only (Gemini every {GEMINI_UPDATE_EVERY_N})")

    return profile
