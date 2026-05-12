"""
core/safety_filter.py — Phase 3: Prompt Hardening

Three defence layers, all rule-based (zero API calls):

  1. sanitize_input()   — strip/normalize dangerous content
  2. check_injection()  — detect prompt injection patterns
  3. check_off_topic()  — flag messages clearly outside educational context

Returns a SafetyResult dataclass so app.py can decide what to show the user.
"""

import re
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

MAX_INPUT_LENGTH = 1000
MIN_INPUT_LENGTH = 2

# Prompt injection patterns (category label used for logging only)
_INJECTION_PATTERNS: list[tuple[str, str]] = [
    (r"ignore\s+(.{0,15}?)(instructions?|rules?|prompts?|directions?)",                                                  "instruction override"),
    (r"disregard\s+(all\s+)?(previous|prior|above|your)\s+(instructions?|rules?|prompts?)",                              "instruction override"),
    (r"forget\s+(everything|all|your\s+instructions?|your\s+rules?|what\s+you\s+(were|are)\s+told)",                    "memory wipe"),
    (r"(override|bypass|circumvent|disable)\s+(your\s+)?(safety|filter|rule|instruction|restriction|guard|limit)",       "safety bypass"),
    (r"(you\s+are\s+now|act|pretend|behave)\s+(as\s+)?(if\s+)?(you\s+)?(are|were\s+)?((a|an)\s+)?(different|new|another|evil|unrestricted|free|uncensored)", "identity hijack"),
    (r"(pretend|imagine)\s+(you\s+(are|were)|to\s+be)\s+(a\s+)?(different|new|another|unrestricted|free)",              "identity hijack"),
    (r"(new|updated|revised|real|actual|true)\s+(system\s+)?prompt\s*[:=\[]",                                            "system prompt injection"),
    (r"\[\s*(system|sys|inst|instruction)\s*\]",                                                                          "system tag injection"),
    (r"<\s*(system|sys|instructions?)\s*>",                                                                               "system tag injection"),
    (r"(exit|leave|step\s+out\s+of|break\s+out\s+of)\s+(your\s+)?(role|character|persona|mode)",                        "role escape"),
    (r"(stop\s+being|stop\s+acting\s+(as|like)|no\s+longer\s+be)\s+(a\s+)?(mentor|coach|assistant|growthmentor)",       "role escape"),
    (r"developer\s+mode",                                                                                                  "developer mode"),
    (r"jailbreak",                                                                                                         "jailbreak attempt"),
    (r"(do\s+anything\s+now|dan\s+mode)",                                                                                 "DAN/jailbreak"),
]

# Clearly harmful content — soft flag only (Gemini's own safety handles most cases)
_OFF_TOPIC_SIGNALS: list[str] = [
    r"\b(porn|sex|nude|explicit|nsfw)\b",
    r"\b(hack|exploit|malware|ransomware|phishing)\b",
    r"\b(bomb|weapon|explosive|kill\s+people)\b",
    r"\b(buy|sell|invest|stock\s+market|crypto|bitcoin)\b",
]

_STRIP_CHARS_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


# ── Result type ───────────────────────────────────────────────────────────────

@dataclass
class SafetyResult:
    is_safe: bool
    sanitized_text: str
    block_reason: str = ""
    warning: str = ""
    flags: list[str] = field(default_factory=list)


# ── Layer 1: Sanitization ─────────────────────────────────────────────────────

def sanitize_input(text: str) -> str:
    """Remove control chars, collapse excess whitespace, strip edges."""
    text = _STRIP_CHARS_PATTERN.sub("", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


# ── Layer 2: Injection detection ──────────────────────────────────────────────

def check_injection(text: str) -> tuple[bool, str]:
    """Scan for prompt injection patterns. Returns (is_injection, category)."""
    lower = text.lower()
    for pattern, category in _INJECTION_PATTERNS:
        if re.search(pattern, lower):
            logger.warning(f"Injection detected [{category}]: '{text[:80]}'")
            return True, category
    return False, ""


# ── Layer 3: Off-topic signals ────────────────────────────────────────────────

def check_off_topic(text: str) -> tuple[bool, str]:
    """Detect clearly harmful/off-topic content. Soft check — not a hard block."""
    lower = text.lower()
    for pattern in _OFF_TOPIC_SIGNALS:
        match = re.search(pattern, lower)
        if match:
            logger.info(f"Off-topic signal: '{match.group()}' in '{text[:60]}'")
            return True, match.group()
    return False, ""


# ── Main entry point ──────────────────────────────────────────────────────────

def run_safety_check(raw_input: str) -> SafetyResult:
    """
    Run all three layers on raw user input.
    Always returns a SafetyResult — safe to use even when blocked.
    """
    flags: list[str] = []

    if len(raw_input.strip()) < MIN_INPUT_LENGTH:
        return SafetyResult(is_safe=False, sanitized_text="",
                            block_reason="Please enter a longer message.",
                            flags=["too_short"])

    if len(raw_input) > MAX_INPUT_LENGTH:
        return SafetyResult(is_safe=False, sanitized_text="",
                            block_reason=f"Message is too long. Please keep it under {MAX_INPUT_LENGTH} characters.",
                            flags=["too_long"])

    cleaned = sanitize_input(raw_input)

    is_injection, category = check_injection(cleaned)
    if is_injection:
        flags.append(f"injection:{category}")
        return SafetyResult(
            is_safe=False,
            sanitized_text=cleaned,
            block_reason=(
                "I can only help you with your learning goal. "
                "Let's keep our session focused — what would you like to learn today?"
            ),
            flags=flags,
        )

    is_off_topic, signal = check_off_topic(cleaned)
    if is_off_topic:
        flags.append(f"off_topic:{signal}")
        logger.info("Off-topic signal passed to Gemini for persona-driven redirect")

    return SafetyResult(is_safe=True, sanitized_text=cleaned, flags=flags)
