"""
Date resolver — turns relative phrases like "Friday 5pm" or "tomorrow by
midnight" into absolute ``datetime`` objects using the message timestamp as
the reference point.
"""

import re
from datetime import datetime, timedelta

import dateparser
from dateutil import tz

from config import DEFAULT_TIMEZONE

# ── Special-phrase normalisation map ──────────────────────────────────────────
_PHRASE_NORMALISATIONS: list[tuple[re.Pattern, str]] = [
    # "by midnight"  →  "at 23:59"
    (re.compile(r"\bmidnight\b", re.I), "23:59"),
    # "end of day" / "EOD"  →  "at 23:59"
    (re.compile(r"\bend\s+of\s+(?:the\s+)?day\b", re.I), "23:59"),
    (re.compile(r"\bEOD\b"), "23:59"),
    # "morning" → "09:00"
    (re.compile(r"\bmorning\b", re.I), "09:00"),
    # "evening" → "18:00"
    (re.compile(r"\bevening\b", re.I), "18:00"),
    # "noon" → "12:00"
    (re.compile(r"\bnoon\b", re.I), "12:00"),
]

# Matches common time tokens so we can detect if a time was included
_TIME_PATTERN = re.compile(
    r"\d{1,2}:\d{2}|\d{1,2}\s*(?:am|pm|AM|PM)|23:59|09:00|18:00|12:00",
)


def _normalise_phrase(phrase: str) -> str:
    """Replace colloquial time references with parseable equivalents."""
    for pattern, replacement in _PHRASE_NORMALISATIONS:
        phrase = pattern.sub(replacement, phrase)
    return phrase.strip()


def resolve_date(
    phrase: str,
    reference_date: datetime,
    timezone: str = DEFAULT_TIMEZONE,
) -> datetime | None:
    """
    Resolve a human-readable date phrase to an absolute ``datetime``.

    Parameters
    ----------
    phrase : str
        The raw date/time phrase extracted from a chat message, e.g.
        ``"Friday 5pm"``, ``"tomorrow by midnight"``, ``"25th October"``.
    reference_date : datetime
        The timestamp of the chat message that contained the phrase.  This is
        used as the "now" anchor so that ``"tomorrow"`` resolves correctly.
    timezone : str
        IANA timezone string (default ``Asia/Kolkata``).

    Returns
    -------
    datetime or None
        The resolved absolute datetime, or ``None`` if parsing fails.
    """
    if not phrase or not phrase.strip():
        return None

    normalised = _normalise_phrase(phrase)
    has_explicit_time = bool(_TIME_PATTERN.search(normalised))

    # dateparser settings
    settings = {
        "RELATIVE_BASE": reference_date.replace(tzinfo=None),
        "TIMEZONE": timezone,
        "RETURN_AS_TIMEZONE_AWARE": False,
        "PREFER_DATES_FROM": "future",          # "Friday" → NEXT Friday
        "PREFER_DAY_OF_MONTH": "first",
    }

    parsed = dateparser.parse(normalised, settings=settings)

    if parsed is None:
        # Try with just the raw phrase (before normalisation) as a fallback
        parsed = dateparser.parse(phrase.strip(), settings=settings)

    if parsed is None:
        return None

    # If no explicit time was present, default to end-of-day (23:59)
    if not has_explicit_time and parsed.hour == 0 and parsed.minute == 0:
        parsed = parsed.replace(hour=23, minute=59, second=0, microsecond=0)

    # Ensure the resolved date is in the future relative to reference
    # (e.g., "Friday" should not resolve to a past Friday)
    if parsed < reference_date:
        # Try nudging by a week for day-of-week phrases
        day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        if any(d in phrase.lower() for d in day_names):
            parsed += timedelta(weeks=1)

    return parsed


def resolve_deadlines(deadlines: list[dict], timezone: str = DEFAULT_TIMEZONE) -> list[dict]:
    """
    Bulk-resolve the ``date_phrase`` field in a list of deadline dicts,
    adding a ``resolved_date`` key to each.

    Parameters
    ----------
    deadlines : list[dict]
        Each dict must have at least ``date_phrase`` (str) and
        ``message_timestamp`` (datetime).
    timezone : str
        IANA timezone string.

    Returns
    -------
    list[dict]
        The same list with an added ``resolved_date`` field (datetime or None).
    """
    for dl in deadlines:
        ref = dl.get("message_timestamp", datetime.now())
        phrase = dl.get("date_phrase", "")
        dl["resolved_date"] = resolve_date(phrase, reference_date=ref, timezone=timezone)
    return deadlines
