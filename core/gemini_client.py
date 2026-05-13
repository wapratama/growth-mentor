import os
import logging
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MODEL_ID = "gemini-2.5-flash"


def _get_client() -> genai.Client:
    """Create and return a Gemini client using the API key from environment."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GEMINI_API_KEY is not set. "
            "Add it to your .env file (locally) or Streamlit secrets (deployed).\n"
            "Get a free key at: https://aistudio.google.com/app/apikey"
        )
    if api_key == "your_gemini_api_key_here":
        raise EnvironmentError(
            "You haven't replaced the placeholder in .env yet.\n"
            "Open .env and replace 'your_gemini_api_key_here' with your real API key.\n"
            "Get a free key at: https://aistudio.google.com/app/apikey"
        )
    return genai.Client(api_key=api_key)


def _build_contents(history: list[dict], user_message: str) -> list[types.Content]:
    """Convert chat history + new message into Gemini Content objects."""
    contents = []
    for msg in history:
        role = "user" if msg["role"] == "user" else "model"
        contents.append(
            types.Content(role=role, parts=[types.Part(text=msg["content"])])
        )
    contents.append(
        types.Content(role="user", parts=[types.Part(text=user_message)])
    )
    return contents


def _categorize_error(e: Exception) -> str:
    """
    Convert a raw API exception into a clear, actionable user message.
    Also logs the real error detail for the developer.
    """
    error_str = str(e).lower()
    raw = str(e)

    logger.error(f"Gemini API error — {type(e).__name__}: {raw}")

    if "401" in raw or "api_key_invalid" in error_str or "unauthenticated" in error_str:
        return (
            "⚠️ **Invalid API key (401)**\n\n"
            "Your API key was rejected by Google. Please:\n"
            "1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey)\n"
            "2. Copy your key\n"
            "3. Paste it into your `.env` file as `GEMINI_API_KEY=...`\n"
            "4. Restart the app"
        )
    if "403" in raw or "permission" in error_str or "forbidden" in error_str:
        return (
            "⚠️ **Permission denied (403)**\n\n"
            "Your API key doesn't have access to this model or the Gemini API is not enabled.\n"
            "Please check that:\n"
            "- You are using a **Gemini Developer API** key (not a Vertex AI key)\n"
            "- The key was created at [aistudio.google.com](https://aistudio.google.com/app/apikey)"
        )
    if "429" in raw or "quota" in error_str or "rate" in error_str:
        return (
            "⚠️ **Rate limit reached (429)**\n\n"
            "You've hit your API quota. Please wait a moment and try again.\n"
            "- **5 requests / minute (RPM)** — wait 60 seconds and retry\n"
            "- **20 requests / day (RPD)** — if hit, try again tomorrow."
        )
    if "timeout" in error_str or "deadline" in error_str:
        return (
            "⚠️ **Request timed out**\n\n"
            "Gemini took too long to respond. Please try again."
        )
    if "network" in error_str or "connection" in error_str or "ssl" in error_str:
        return (
            "⚠️ **Network error**\n\n"
            "Cannot reach the Gemini API. Please check your internet connection."
        )

    # Fallback: show the real error so it can be debugged
    return (
        f"⚠️ **Unexpected error — please share this with the developer:**\n\n"
        f"`{type(e).__name__}: {raw[:300]}`"
    )


def _call_gemini(
    client: genai.Client,
    contents: list,
    system_prompt: str,
    use_search: bool,
) -> str:
    """Single Gemini call. Raises on failure so caller can handle fallback."""
    tools = [types.Tool(google_search=types.GoogleSearch())] if use_search else []
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        tools=tools,
        max_output_tokens=512,
        temperature=0.7,
    )
    response = client.models.generate_content(
        model=MODEL_ID,
        contents=contents,
        config=config,
    )
    return response.text or "I didn't generate a response. Please try again."


def generate_response(
    user_message: str,
    system_prompt: str,
    history: list[dict],
    use_search: bool = True,
) -> str:
    """
    Send a message to Gemini and return the text response.

    Tries with Google Search grounding first.
    If that fails due to a search-specific error, retries without search.
    All other errors are surfaced with clear, actionable messages.

    Args:
        user_message:  The raw text from the user's input box.
        system_prompt: The fully built system prompt (persona + memory context).
        history:       The last N chat messages for context.
        use_search:    Whether to attempt Google Search grounding (default True).

    Returns:
        The model's response as a plain string, or a formatted error message.
    """
    try:
        client = _get_client()
    except EnvironmentError as e:
        logger.error(f"Config error: {e}")
        return f"⚠️ **Configuration error**\n\n{e}"

    contents = _build_contents(history, user_message)

    # Attempt 1: with search grounding
    if use_search:
        try:
            logger.info(f"Calling Gemini | model={MODEL_ID} | search=True | history={len(history)}")
            return _call_gemini(client, contents, system_prompt, use_search=True)
        except Exception as e:
            error_str = str(e).lower()
            # Only fall back to no-search for search-specific errors
            if any(k in error_str for k in ["google_search", "tool", "grounding", "search"]):
                logger.warning("Search grounding failed — retrying without search")
            else:
                return _categorize_error(e)

    # Attempt 2: without search grounding
    try:
        logger.info(f"Calling Gemini | model={MODEL_ID} | search=False | history={len(history)}")
        return _call_gemini(client, contents, system_prompt, use_search=False)
    except Exception as e:
        return _categorize_error(e)
