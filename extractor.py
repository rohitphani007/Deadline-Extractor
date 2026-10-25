"""
Core AI extraction module — sends chat messages to a local Ollama model
and extracts structured deadline / assignment information.
"""

import json
import sys
from typing import Callable

import ollama

import config

# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a deadline extraction assistant. You analyze chat messages and identify if they contain any assignment deadlines, due dates, or submission requirements.

For each message, determine:
1. Is there a deadline or assignment mentioned? (yes/no)
2. If yes, extract:
   - task: What needs to be done (e.g., "Submit ML assignment", "Upload lab report")
   - date_phrase: The exact date/time phrase from the message (e.g., "Friday 5pm", "tomorrow by midnight", "25th October")
   - subject: The course or subject if mentioned (e.g., "Machine Learning", "DBMS")
   - urgency: "high" if today/tomorrow, "medium" if this week, "low" if later

IMPORTANT RULES:
- Only extract REAL deadlines. Ignore casual mentions like "we had a deadline last week"
- If someone says "deadline extended to Monday", that's a NEW deadline that overrides the old one
- Ignore jokes, memes, and casual conversation
- If unsure, skip the message rather than inventing a deadline

Respond with valid JSON only. If no deadline found, respond with: {"has_deadline": false}
If deadline found, respond with:
{"has_deadline": true, "task": "...", "date_phrase": "...", "subject": "...", "urgency": "..."}"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_user_prompt(message_text: str, context_messages: list[str] | None = None) -> str:
    """
    Build the user-side prompt containing the target message and optional
    surrounding context.
    """
    parts: list[str] = []
    if context_messages:
        parts.append("=== Context (surrounding messages for reference) ===")
        for ctx in context_messages:
            parts.append(f"  - {ctx}")
        parts.append("")
    parts.append("=== Message to analyze ===")
    parts.append(message_text)
    return "\n".join(parts)


def _parse_json_response(raw: str) -> dict | None:
    """
    Attempt to extract a JSON object from the model's raw response text.
    Handles cases where the model wraps JSON in markdown fences or adds
    extra commentary.
    """
    raw = raw.strip()

    # Strip markdown code fences if present
    if raw.startswith("```"):
        lines = raw.splitlines()
        # Remove first and last fence lines
        json_lines = [l for l in lines if not l.strip().startswith("```")]
        raw = "\n".join(json_lines).strip()

    # Try direct parse first
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Try to find the first { ... } block
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            pass

    return None


def _check_ollama_available() -> bool:
    """Return True if the Ollama server is reachable."""
    try:
        ollama.list()
        return True
    except Exception:
        return False


# ── Public API ────────────────────────────────────────────────────────────────

def extract_single(message_text: str, context_messages: list[str] | None = None) -> dict | None:
    """
    Send a single message (with optional surrounding context) to the Ollama
    model and return a parsed deadline dict, or ``None`` if no deadline is
    found or the model is unavailable.

    Parameters
    ----------
    message_text : str
        The chat message to analyse.
    context_messages : list[str], optional
        A few surrounding messages to give the model conversational context.

    Returns
    -------
    dict or None
        Parsed deadline information, or None.
    """
    user_prompt = _build_user_prompt(message_text, context_messages)

    for attempt in range(1, config.MAX_RETRIES + 2):  # 1 initial + MAX_RETRIES retries
        try:
            response = ollama.chat(
                model=config.MODEL_NAME,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
            )
            raw_text = response["message"]["content"]
            parsed = _parse_json_response(raw_text)

            if parsed is not None:
                if parsed.get("has_deadline") is True:
                    return parsed
                else:
                    return None  # Model explicitly said no deadline

            # JSON parsing failed – retry
            if attempt <= config.MAX_RETRIES:
                continue
            return None

        except ollama.ResponseError as exc:
            print(f"  ⚠  Ollama response error: {exc}", file=sys.stderr)
            return None
        except Exception as exc:
            print(f"  ⚠  Ollama error: {exc}", file=sys.stderr)
            return None

    return None


def extract_deadlines_from_messages(
    messages: list[dict],
    batch_size: int = 3,
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[dict]:
    """
    Process a list of chat messages and extract deadlines.

    Each message is sent to the model along with a small window of surrounding
    messages for conversational context.  Extracted deadlines are enriched
    with the original message's timestamp and author.

    Parameters
    ----------
    messages : list[dict]
        Output of ``chat_parser.parse_chat`` — each dict has keys
        ``timestamp``, ``author``, ``text``.
    batch_size : int
        (Unused directly) kept for API compatibility.  Context window is
        controlled by ``config.BATCH_CONTEXT_SIZE``.
    progress_callback : callable, optional
        Called as ``progress_callback(current_index, total)`` after each
        message is processed.

    Returns
    -------
    list[dict]
        List of deadline dicts.  Each contains the model-extracted fields
        plus ``message_timestamp``, ``posted_by``, and ``original_message``.
    """
    if not _check_ollama_available():
        print("❌ Ollama is not running. Please start it with 'ollama serve'.", file=sys.stderr)
        return []

    total = len(messages)
    deadlines: list[dict] = []

    for idx, msg in enumerate(messages):
        # Build context window
        start = max(0, idx - config.BATCH_CONTEXT_SIZE)
        end = min(total, idx + config.BATCH_CONTEXT_SIZE + 1)
        context = [
            f"[{messages[j]['author']}]: {messages[j]['text']}"
            for j in range(start, end)
            if j != idx
        ]

        message_text = f"[{msg['author']}]: {msg['text']}"

        result = extract_single(message_text, context_messages=context)

        if result is not None:
            result["message_timestamp"] = msg["timestamp"]
            result["posted_by"] = msg["author"]
            result["original_message"] = msg["text"]
            deadlines.append(result)

        # Progress reporting
        if progress_callback is not None:
            progress_callback(idx + 1, total)

    return deadlines
