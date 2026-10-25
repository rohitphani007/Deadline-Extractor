"""
Deduplication module — removes duplicate deadlines and correctly handles
updates / extensions (e.g. "deadline extended to Monday").
"""

import re
from difflib import SequenceMatcher

# ── Thresholds ────────────────────────────────────────────────────────────────
_SIMILARITY_THRESHOLD = 0.60  # tasks with similarity ≥ this are considered dupes

# Phrases that indicate a deadline update / extension
_UPDATE_PHRASES = re.compile(
    r"\b(extend(?:ed)?|postpon(?:ed)?|push(?:ed)?\s*back|reschedul(?:ed)?|"
    r"move[ds]?\s+to|shift(?:ed)?|new\s+deadline|updated?\s+deadline|"
    r"chang(?:ed|e)\s+(?:the\s+)?(?:deadline|date))\b",
    re.IGNORECASE,
)


def _normalise_task(task: str) -> str:
    """Lower-case, strip, collapse whitespace for comparison."""
    return re.sub(r"\s+", " ", task.strip().lower())


def _similarity(a: str, b: str) -> float:
    """Return the SequenceMatcher similarity ratio between two strings."""
    return SequenceMatcher(None, _normalise_task(a), _normalise_task(b)).ratio()


def _is_update_message(deadline: dict) -> bool:
    """Return True if the original message indicates a date update/extension."""
    text = deadline.get("original_message", "") or ""
    return bool(_UPDATE_PHRASES.search(text))


def deduplicate_deadlines(deadlines: list[dict]) -> list[dict]:
    """
    Remove duplicate deadlines and handle updates / extensions.

    Rules
    -----
    1. If two deadlines have the same task (fuzzy match ≥ 60 %), keep the one
       with the later ``message_timestamp`` — it is the more recent update.
    2. If a message explicitly says "extended", "postponed", etc., the newer
       deadline's date overrides the older one.
    3. Results are optionally grouped by ``subject`` if available.

    Parameters
    ----------
    deadlines : list[dict]
        Each dict should contain at least ``task``, ``message_timestamp``,
        and optionally ``subject``, ``resolved_date``, ``original_message``.

    Returns
    -------
    list[dict]
        Deduplicated list, sorted by ``resolved_date`` (earliest first),
        then by ``subject``.
    """
    if not deadlines:
        return []

    # Sort so that when we encounter duplicates, the *latest* message wins
    sorted_dls = sorted(deadlines, key=lambda d: d.get("message_timestamp", 0))

    unique: list[dict] = []

    for dl in sorted_dls:
        task = dl.get("task", "")
        subject = (dl.get("subject") or "").strip().lower()

        matched_idx: int | None = None
        best_score = 0.0

        for idx, existing in enumerate(unique):
            existing_task = existing.get("task", "")
            existing_subject = (existing.get("subject") or "").strip().lower()

            score = _similarity(task, existing_task)

            # Boost score if subjects also match
            if subject and existing_subject and _similarity(subject, existing_subject) > 0.6:
                score = min(score + 0.15, 1.0)

            if score >= _SIMILARITY_THRESHOLD and score > best_score:
                best_score = score
                matched_idx = idx

        if matched_idx is not None:
            # Duplicate found — replace with the newer one (current dl is later
            # in time because we sorted by timestamp)
            existing = unique[matched_idx]

            # If the new message is an explicit update, take its resolved_date
            if _is_update_message(dl):
                existing["resolved_date"] = dl.get("resolved_date", existing.get("resolved_date"))
                existing["date_phrase"] = dl.get("date_phrase", existing.get("date_phrase"))

            # Always update metadata to the latest message
            existing["message_timestamp"] = dl.get("message_timestamp", existing.get("message_timestamp"))
            existing["posted_by"] = dl.get("posted_by", existing.get("posted_by"))
            existing["original_message"] = dl.get("original_message", existing.get("original_message"))
            existing["urgency"] = dl.get("urgency", existing.get("urgency"))

            # Keep the more descriptive task name (longer usually = more detail)
            if len(task) > len(existing.get("task", "")):
                existing["task"] = task

            # Prefer a non-empty subject
            if dl.get("subject") and not existing.get("subject"):
                existing["subject"] = dl["subject"]
        else:
            unique.append(dict(dl))  # copy to avoid mutation

    # Sort final list: by resolved_date (None last), then subject
    def _sort_key(d: dict):
        rd = d.get("resolved_date")
        subj = (d.get("subject") or "zzz").lower()
        # Use a very far future date for None so they sort last
        from datetime import datetime
        rd_val = rd if rd is not None else datetime(9999, 12, 31)
        return (rd_val, subj)

    unique.sort(key=_sort_key)

    return unique
