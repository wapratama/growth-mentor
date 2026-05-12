"""
core/quiz_engine.py — Phase 4: Quiz Generator

Generates 3-question multiple-choice quizzes using a single Gemini call.
Scoring updates the learner's confidence scores in their profile.

Cost: 1 API call per quiz (user-triggered only, never automatic).

Flow:
  generate_quiz(profile)     → Quiz dataclass (3 MCQ questions + explanations)
  score_quiz(quiz, answers)  → (correct_count, total)
  confidence_from_score(pct) → int 1–5 (used to update profile.confidence)
"""

import os
import re
import json
import logging
from dataclasses import dataclass, field
from dotenv import load_dotenv
from google import genai
from google.genai import types
from memory.profile import UserProfile

load_dotenv()
logger = logging.getLogger(__name__)

MODEL_ID = "gemini-2.5-flash"
NUM_QUESTIONS = 3   # kept low to respect RPD and token budget

# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class QuizQuestion:
    question: str
    options: list[str]        # exactly 4 options
    correct_index: int        # 0-based index into options
    explanation: str          # shown after answering


@dataclass
class Quiz:
    topic: str
    questions: list[QuizQuestion]
    score: int | None = None              # set after submission
    total: int = NUM_QUESTIONS
    persona: str = "guardiola"            # used to style result message


# ── Gemini prompt ─────────────────────────────────────────────────────────────

_QUIZ_PROMPT = """You are a quiz generator for a personal learning coach app.

Learner's goal: {goal}
Topic to quiz on: {topic}
Difficulty hint — learner's current confidence on this topic: {confidence}/5

Generate exactly {n} multiple-choice questions about "{topic}" in the context of "{goal}".

Rules:
- Each question must have exactly 4 options (no more, no less)
- Exactly one option is correct
- Options must be meaningfully different (not trivially distinguishable)
- Explanations must be concise (1–2 sentences) and educational
- Difficulty should match the confidence level (low confidence = simpler questions)
- Do not repeat question patterns

Respond ONLY with a valid JSON array. No markdown. No explanation. No preamble.
Use exactly this structure:
[
  {{
    "question": "<the question text>",
    "options": ["<option A>", "<option B>", "<option C>", "<option D>"],
    "correct_index": <0, 1, 2, or 3>,
    "explanation": "<why the correct answer is right>"
  }}
]
"""


# ── Generation ────────────────────────────────────────────────────────────────

def generate_quiz(profile: UserProfile) -> Quiz | None:
    """
    Call Gemini to generate a quiz on the learner's current topic.
    Returns a Quiz dataclass, or None if generation fails.

    Uses no search grounding (quiz content is knowledge-based, not time-sensitive).
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY not set — cannot generate quiz")
        return None

    # Determine topic: prefer current_topic, fall back to learning_goal
    topic = profile.current_topic or profile.learning_goal or "general knowledge"
    confidence = profile.confidence.get(topic, 0)

    prompt = _QUIZ_PROMPT.format(
        goal=profile.learning_goal,
        topic=topic,
        confidence=confidence,
        n=NUM_QUESTIONS,
    )

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
            config=types.GenerateContentConfig(
                max_output_tokens=1024,
                temperature=0.4,   # moderate creativity, consistent structure
            ),
        )

        raw = response.text or ""
        logger.info(f"Quiz generation raw ({len(raw)} chars): {raw[:100]}")

        questions = _parse_quiz(raw)
        if not questions:
            logger.error("Quiz parsing failed — no valid questions extracted")
            return None

        return Quiz(topic=topic, questions=questions,
                    total=len(questions), persona=profile.persona)

    except Exception as e:
        logger.error(f"Quiz generation failed: {e}")
        return None


def _parse_quiz(raw: str) -> list[QuizQuestion]:
    """
    Parse the JSON array from Gemini's quiz response.
    Strips markdown fences, validates structure, returns list of QuizQuestion.
    Returns empty list on any parse failure.
    """
    # Strip markdown fences
    cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()

    # Find outermost JSON array
    match = re.search(r"\[.*\]", cleaned, re.DOTALL)
    if not match:
        logger.warning("No JSON array found in quiz response")
        return []

    try:
        data = json.loads(match.group())
    except json.JSONDecodeError as e:
        logger.warning(f"JSON parse error in quiz response: {e}")
        return []

    questions: list[QuizQuestion] = []
    for i, item in enumerate(data):
        # Validate required fields
        if not all(k in item for k in ("question", "options", "correct_index", "explanation")):
            logger.warning(f"Question {i} missing required fields — skipping")
            continue
        if not isinstance(item["options"], list) or len(item["options"]) != 4:
            logger.warning(f"Question {i} has wrong number of options — skipping")
            continue
        if not isinstance(item["correct_index"], int) or not (0 <= item["correct_index"] <= 3):
            logger.warning(f"Question {i} has invalid correct_index — skipping")
            continue

        questions.append(QuizQuestion(
            question=str(item["question"]).strip(),
            options=[str(o).strip() for o in item["options"]],
            correct_index=int(item["correct_index"]),
            explanation=str(item["explanation"]).strip(),
        ))

    return questions


# ── Scoring ───────────────────────────────────────────────────────────────────

def score_quiz(
    quiz: Quiz,
    user_answers: dict[int, int],   # {question_index: selected_option_index}
) -> tuple[int, int]:
    """
    Score the quiz.
    Returns (correct_count, total_questions).
    Missing answers are counted as wrong.
    """
    correct = 0
    for i, q in enumerate(quiz.questions):
        if user_answers.get(i) == q.correct_index:
            correct += 1
    quiz.score = correct
    return correct, len(quiz.questions)


def confidence_from_score(correct: int, total: int) -> int:
    """
    Map quiz score percentage to a confidence score (1–5).
    Used to update profile.confidence after a quiz.

      0–20%  → 1 (Beginner)
      21–40% → 2 (Familiar)
      41–60% → 3 (Comfortable)
      61–80% → 4 (Confident)
      81–100%→ 5 (Mastered)
    """
    if total == 0:
        return 0
    pct = correct / total
    if pct <= 0.20:   return 1
    if pct <= 0.40:   return 2
    if pct <= 0.60:   return 3
    if pct <= 0.80:   return 4
    return 5


# ── Result message (persona-aware) ───────────────────────────────────────────

def build_result_message(quiz: Quiz, correct: int, total: int) -> str:
    """Generate a persona-appropriate result message."""
    pct = int((correct / total) * 100) if total else 0
    topic = quiz.topic

    messages = {
        "klopp": {
            5: f"INCREDIBLE! {correct}/{total} on {topic}! That's absolutely world-class — you're on FIRE! 🔥",
            4: f"YES! {correct}/{total}! You're really getting this, I can feel it! One more push and it's perfect!",
            3: f"Good effort — {correct}/{total}! We're on the right track. A bit more practice and you'll nail it!",
            2: f"Hey, {correct}/{total} is a start! Don't worry — we attack this together. Let's review the gaps!",
            1: f"{correct}/{total}... But you know what? This is where champions are born. Let's go again!",
        },
        "guardiola": {
            5: f"{correct}/{total}. Excellent. You understand {topic} at the level I expect. We move forward.",
            4: f"{correct}/{total}. Good, but not complete. Identify the one you missed and tell me exactly why.",
            3: f"{correct}/{total}. The foundation is there. The gaps are specific — let's address each one.",
            2: f"{correct}/{total}. The understanding of {topic} is not yet solid. We go back to first principles.",
            1: f"{correct}/{total}. We have significant work to do on {topic}. That is honest feedback. Let's begin.",
        },
        "mourinho": {
            5: f"{correct}/{total}. Perfect score. That's what I expect from my players. Now do it under pressure.",
            4: f"{correct}/{total}. Almost. Champions don't accept 'almost'. Find the mistake. Fix it.",
            3: f"{correct}/{total}. Half-decent. In a real exam that barely passes. What's your excuse for the rest?",
            2: f"{correct}/{total}. Not good enough. But I've seen worse come back stronger. Your move.",
            1: f"{correct}/{total}. Rock bottom. Good. Now you know exactly where to start. No excuses.",
        },
    }

    # Pick tier based on score
    tier = 5 if pct == 100 else 4 if pct >= 80 else 3 if pct >= 60 else 2 if pct >= 40 else 1
    persona = quiz.persona if quiz.persona in messages else "guardiola"
    return messages[persona][tier]


# ── Intent detection (used in app.py) ────────────────────────────────────────

_QUIZ_TRIGGERS = re.compile(
    r"\b(quiz\s*me|test\s*me|give\s*me\s*a\s*(quiz|test)|"
    r"quiz\s*(time|please|now)|let'?s\s*(quiz|test)|"
    r"challenge\s*me|can\s*you\s*(quiz|test)\s*me)\b",
    re.IGNORECASE,
)


def is_quiz_request(text: str) -> bool:
    """Return True if the user's message is asking for a quiz."""
    return bool(_QUIZ_TRIGGERS.search(text))
