from pydantic import BaseModel, Field
from typing import Literal


class UserProfile(BaseModel):
    name: str = ""
    learning_goal: str = ""
    current_topic: str = ""
    topics_covered: list[str] = Field(default_factory=list)
    confidence: dict[str, int] = Field(default_factory=dict)
    last_session_summary: str = ""
    session_count: int = 0
    # Empty string = not chosen yet. Must be set explicitly during onboarding Step 2.
    persona: Literal["", "klopp", "guardiola", "mourinho"] = ""

    def is_complete(self) -> bool:
        """Returns True only when all three onboarding fields are explicitly set."""
        return bool(self.name and self.learning_goal and self.persona)

    def display_confidence(self, topic: str) -> str:
        """Returns a human-readable confidence label for a topic."""
        score = self.confidence.get(topic, 0)
        labels = {0: "Not started", 1: "Beginner", 2: "Familiar",
                  3: "Comfortable", 4: "Confident", 5: "Mastered"}
        return labels.get(score, "Unknown")
