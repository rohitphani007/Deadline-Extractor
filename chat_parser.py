"""
Chat parser module — parses exported chat files from WhatsApp, Telegram,
and a generic line-by-line format.

Main entry point:
    parse_chat(file_path_or_text, format="auto") -> list[dict]
"""

import re
from datetime import datetime
from pathlib import Path

from config import SUPPORTED_CHAT_FORMATS

# ── WhatsApp regex patterns ───────────────────────────────────────────────────
# Pattern 1: "25/10/23, 9:41 pm - Author: message"  (Android / iOS common)
_WA_PATTERN_1 = re.compile(
    r"^(\d{1,2}/\d{1,2}/\d{2,4},\s*\d{1,2}:\d{2}(?::\d{2})?\s*[APap][Mm])\s*-\s*(.+?):\s(.+)",
    re.UNICODE,
)

# Pattern 2: "[25/10/23, 9:41:23 PM] Author: message"  (bracketed variant)
_WA_PATTERN_2 = re.compile(
    r"^\[(\d{1,2}/\d{1,2}/\d{2,4},\s*\d{1,2}:\d{2}(?::\d{2})?\s*[APap][Mm])\]\s*(.+?):\s(.+)",
    re.UNICODE,
)

# Pattern 3: "25/10/23, 21:41 - Author: message" (24-hour, no AM/PM)
_WA_PATTERN_3 = re.compile(
    r"^(\d{1,2}/\d{1,2}/\d{2,4},\s*\d{1,2}:\d{2}(?::\d{2})?)\s*-\s*(.+?):\s(.+)",
    re.UNICODE,
)

# Ordered so the more specific bracketed pattern is tried first
_WA_PATTERNS = [_WA_PATTERN_2, _WA_PATTERN_1, _WA_PATTERN_3]

# WhatsApp date-stamp formats for strptime (tried in order)
_WA_DT_FORMATS = [
    "%d/%m/%y, %I:%M %p",
    "%d/%m/%Y, %I:%M %p",
    "%d/%m/%y, %I:%M:%S %p",
    "%d/%m/%Y, %I:%M:%S %p",
    "%d/%m/%y, %H:%M",
    "%d/%m/%Y, %H:%M",
    "%d/%m/%y, %H:%M:%S",
    "%d/%m/%Y, %H:%M:%S",
    "%m/%d/%y, %I:%M %p",
    "%m/%d/%Y, %I:%M %p",
]

# ── Telegram regex pattern ────────────────────────────────────────────────────
# Very loose: "Author  [timestamp]" or just lines of text
_TG_PATTERN = re.compile(
    r"^(.+?)\s{2,}\[?(\d{1,2}[./]\d{1,2}[./]\d{2,4}[\s,]+\d{1,2}:\d{2}(?::\d{2})?(?:\s*[APap][Mm])?)\]?\s*$",
    re.UNICODE,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_wa_timestamp(raw: str) -> datetime | None:
    """Try multiple strptime formats to parse a WhatsApp timestamp string."""
    raw = raw.strip().replace("\u202F", " ").replace("\u00A0", " ")
    # Normalise AM/PM to uppercase without altering the rest of the string
    raw_normalised = re.sub(r"(?i)\b(am|pm)\b", lambda m: m.group(1).upper(), raw)
    
    for fmt in _WA_DT_FORMATS:
        try:
            return datetime.strptime(raw_normalised, fmt)
        except ValueError:
            continue

    # Fallback to dateparser for unexpected formats
    try:
        import dateparser
        return dateparser.parse(raw_normalised, settings={"DATE_ORDER": "DMY"})
    except Exception:
        return None


def _try_whatsapp_line(line: str) -> tuple[datetime, str, str] | None:
    """Return (timestamp, author, text) if the line matches a WA pattern."""
    for pattern in _WA_PATTERNS:
        m = pattern.match(line)
        if m:
            ts = _parse_wa_timestamp(m.group(1))
            if ts:
                return ts, m.group(2).strip(), m.group(3).strip()
    return None


def _detect_format(lines: list[str]) -> str:
    """Auto-detect the chat format by inspecting the first non-empty lines."""
    sample = [l for l in lines[:20] if l.strip()]
    wa_hits = sum(1 for l in sample if _try_whatsapp_line(l) is not None)
    if wa_hits >= 2 or (wa_hits >= 1 and len(sample) <= 3):
        return "whatsapp"
    tg_hits = sum(1 for l in sample if _TG_PATTERN.match(l))
    if tg_hits >= 2:
        return "telegram"
    return "generic"


# ── Format-specific parsers ───────────────────────────────────────────────────

def _parse_whatsapp(lines: list[str]) -> list[dict]:
    """Parse WhatsApp exported chat lines into message dicts."""
    messages: list[dict] = []
    for line in lines:
        result = _try_whatsapp_line(line)
        if result:
            ts, author, text = result
            messages.append({"timestamp": ts, "author": author, "text": text})
        else:
            # Continuation of the previous message (multi-line)
            if messages and line.strip():
                messages[-1]["text"] += "\n" + line.strip()
    return messages


def _parse_telegram(lines: list[str]) -> list[dict]:
    """Parse Telegram-style exported chat lines."""
    messages: list[dict] = []
    for line in lines:
        m = _TG_PATTERN.match(line)
        if m:
            author = m.group(1).strip()
            raw_ts = m.group(2).strip()
            ts = _parse_wa_timestamp(raw_ts)  # reuse – similar formats
            if ts is None:
                ts = datetime.now()
            messages.append({"timestamp": ts, "author": author, "text": ""})
        else:
            if messages and line.strip():
                if messages[-1]["text"]:
                    messages[-1]["text"] += "\n" + line.strip()
                else:
                    messages[-1]["text"] = line.strip()
            elif line.strip():
                # Standalone line with no header – treat as generic
                messages.append(
                    {"timestamp": datetime.now(), "author": "Unknown", "text": line.strip()}
                )
    return messages


def _parse_generic(lines: list[str]) -> list[dict]:
    """Each non-empty line is treated as a separate message with the current time."""
    now = datetime.now()
    messages: list[dict] = []
    for line in lines:
        stripped = line.strip()
        if stripped:
            messages.append({"timestamp": now, "author": "Unknown", "text": stripped})
    return messages


# ── Public API ────────────────────────────────────────────────────────────────

def parse_chat(file_path_or_text: str, format: str = "auto") -> list[dict]:
    """
    Parse an exported chat into a list of message dicts.

    Parameters
    ----------
    file_path_or_text : str
        Either a filesystem path to a .txt chat export **or** the raw text
        content of the chat.
    format : str
        One of ``"whatsapp"``, ``"telegram"``, ``"generic"``, or ``"auto"``
        (default).  ``"auto"`` inspects the first few lines and picks the
        best parser.

    Returns
    -------
    list[dict]
        Each dict has keys ``"timestamp"`` (datetime), ``"author"`` (str),
        and ``"text"`` (str).
    """
    # Read input ──────────────────────────────────────────────────────────
    path = Path(file_path_or_text)
    if path.is_file():
        raw_text = path.read_text(encoding="utf-8", errors="replace")
    else:
        raw_text = file_path_or_text

    lines = raw_text.splitlines()

    # Determine format ────────────────────────────────────────────────────
    fmt = format.lower().strip()
    if fmt == "auto":
        fmt = _detect_format(lines)

    if fmt not in SUPPORTED_CHAT_FORMATS:
        raise ValueError(
            f"Unsupported format '{fmt}'. Choose from {SUPPORTED_CHAT_FORMATS} or 'auto'."
        )

    # Dispatch ────────────────────────────────────────────────────────────
    parser_map = {
        "whatsapp": _parse_whatsapp,
        "telegram": _parse_telegram,
        "generic": _parse_generic,
    }

    messages = parser_map[fmt](lines)

    if not messages:
        # Fall back to generic so the user always gets *something*
        messages = _parse_generic(lines)

    return messages
