from pydantic import BaseModel, Field
from typing import Literal


class UserProfile(BaseModel):
    # ── Onboarding fields ───────────────────────────────────────────────────
    name: str = ""
    learning_goal: str = ""
    # Empty string = not chosen yet. Must be set during onboarding Step 2.
    persona: Literal["", "klopp", "guardiola", "mourinho"] = ""

    # ── Learning progress ───────────────────────────────────────────────────
    current_topic: str = ""
    topics_covered: list[str] = Field(default_factory=list)
    confidence: dict[str, int] = Field(default_factory=dict)   # topic → 1–5
    last_session_summary: str = ""
    session_count: int = 0

    # ── Quiz stats (Phase 4) ────────────────────────────────────────────────
    quizzes_taken: int = 0
    quiz_total_questions: int = 0
    quiz_correct_answers: int = 0
    quiz_history: list[dict] = Field(default_factory=list)
    # each entry: {"topic": str, "score": int, "total": int, "pct": int}

    # ── Computed helpers ────────────────────────────────────────────────────
    def is_complete(self) -> bool:
        """True only when all three onboarding fields are explicitly set."""
        return bool(self.name and self.learning_goal and self.persona)

    def display_confidence(self, topic: str) -> str:
        """Human-readable confidence label for a topic."""
        score = self.confidence.get(topic, 0)
        labels = {0: "Not started", 1: "Beginner", 2: "Familiar",
                  3: "Comfortable", 4: "Confident", 5: "Mastered"}
        return labels.get(score, "Unknown")

    def overall_accuracy(self) -> float:
        """Return overall quiz accuracy as a percentage (0.0–100.0)."""
        if self.quiz_total_questions == 0:
            return 0.0
        return round(self.quiz_correct_answers / self.quiz_total_questions * 100, 1)

    def record_quiz(self, topic: str, correct: int, total: int) -> None:
        """Update quiz stats after a quiz is submitted."""
        self.quizzes_taken += 1
        self.quiz_total_questions += total
        self.quiz_correct_answers += correct
        pct = int(correct / total * 100) if total else 0
        self.quiz_history.append({"topic": topic, "score": correct,
                                   "total": total, "pct": pct})
        # Cap history at last 20 quizzes
        if len(self.quiz_history) > 20:
            self.quiz_history = self.quiz_history[-20:]
