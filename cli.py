"""
CLI entry point — pretty terminal interface for the Assignment & Deadline
Extractor.

Usage:
    python cli.py chat_export.txt
    python cli.py chat_export.txt -f whatsapp -o my_deadlines.ics
    python cli.py chat_export.txt --json --no-calendar
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from chat_parser import parse_chat
from extractor import extract_deadlines_from_messages
from date_resolver import resolve_deadlines
from deduplicator import deduplicate_deadlines
from calendar_export import save_calendar
from config import DATETIME_OUTPUT_FORMAT, MODEL_NAME


# ── Pretty-printing helpers ──────────────────────────────────────────────────

def _hr(char: str = "─", width: int = 72) -> str:
    return char * width


def _header() -> str:
    return (
        "\n"
        "  ╔══════════════════════════════════════════════════════════════╗\n"
        "  ║   🦥  Assignment & Deadline Extractor                      ║\n"
        "  ║   Never scroll through 500 messages again.                 ║\n"
        "  ╚══════════════════════════════════════════════════════════════╝\n"
    )


def _urgency_badge(urgency: str) -> str:
    mapping = {
        "high": "🔴 HIGH",
        "medium": "🟡 MED ",
        "low": "🟢 LOW ",
    }
    return mapping.get((urgency or "").lower(), "⚪ ???  ")


def _print_table(deadlines: list[dict]) -> None:
    """Print a nicely formatted summary table to stdout."""
    if not deadlines:
        print("\n  😴 No deadlines found.\n")
        return

    # Column widths
    cw = {"num": 4, "task": 30, "subject": 16, "date": 22, "by": 14, "urg": 10}
    total = sum(cw.values()) + 5 * 3 + 4  # separators

    print()
    print(f"  ┌{'─' * (total)}┐")
    print(
        f"  │ {'#':<{cw['num']}} │ "
        f"{'Task':<{cw['task']}} │ "
        f"{'Subject':<{cw['subject']}} │ "
        f"{'Due Date':<{cw['date']}} │ "
        f"{'Posted By':<{cw['by']}} │ "
        f"{'Urgency':<{cw['urg']}} │"
    )
    print(f"  ├{'─' * (total)}┤")

    for i, dl in enumerate(deadlines, 1):
        task = (dl.get("task") or "—")[:cw["task"]]
        subject = (dl.get("subject") or "—")[:cw["subject"]]
        rd = dl.get("resolved_date")
        date_str = rd.strftime(DATETIME_OUTPUT_FORMAT) if rd else (dl.get("date_phrase") or "—")
        date_str = date_str[:cw["date"]]
        by = (dl.get("posted_by") or "—")[:cw["by"]]
        urg = _urgency_badge(dl.get("urgency", ""))

        print(
            f"  │ {i:<{cw['num']}} │ "
            f"{task:<{cw['task']}} │ "
            f"{subject:<{cw['subject']}} │ "
            f"{date_str:<{cw['date']}} │ "
            f"{by:<{cw['by']}} │ "
            f"{urg:<{cw['urg']}} │"
        )

    print(f"  └{'─' * (total)}┘")
    print()


def _progress(current: int, total: int) -> None:
    """Inline progress indicator for terminal."""
    bar_len = 30
    filled = int(bar_len * current / total) if total else 0
    bar = "█" * filled + "░" * (bar_len - filled)
    pct = (current / total * 100) if total else 0
    print(f"\r  ⏳ Processing message {current}/{total}  [{bar}] {pct:5.1f}%", end="", flush=True)
    if current == total:
        print()  # newline when done


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="deadline-extractor",
        description=(
            "🦥 Extract assignment deadlines from group chat exports. "
            "Never scroll through 500 messages again."
        ),
        epilog="Built with open-source AI for Hacktoberfest 2024 🎃",
    )
    parser.add_argument("chat_file", help="Path to exported chat file (.txt)")
    parser.add_argument(
        "-f", "--format",
        choices=["whatsapp", "telegram", "generic", "auto"],
        default="auto",
        help="Chat format (default: auto-detect)",
    )
    parser.add_argument(
        "-o", "--output",
        default="deadlines.ics",
        help="Output .ics file path (default: deadlines.ics)",
    )
    parser.add_argument(
        "--no-calendar",
        action="store_true",
        help="Skip calendar export",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output results as JSON",
    )
    parser.add_argument(
        "--model",
        default=None,
        help=f"Override Ollama model name (default: {MODEL_NAME})",
    )

    args = parser.parse_args()

    # Override model if requested
    if args.model:
        import config
        config.MODEL_NAME = args.model

    # ── 0. Validate input ────────────────────────────────────────────────
    chat_path = Path(args.chat_file)
    if not chat_path.is_file():
        print(f"  ❌ File not found: {chat_path}", file=sys.stderr)
        sys.exit(1)

    print(_header())

    # ── 1. Parse chat ────────────────────────────────────────────────────
    print(f"  📂 Reading: {chat_path.name}")
    messages = parse_chat(str(chat_path), format=args.format)
    print(f"  💬 Parsed {len(messages)} messages")
    print(f"  {_hr()}")

    if not messages:
        print("  😕 No messages found. Check the file format.")
        sys.exit(0)

    # ── 2. Extract deadlines with AI ─────────────────────────────────────
    print(f"  🤖 Using model: {MODEL_NAME}")
    print(f"  🔍 Scanning for deadlines…\n")

    deadlines = extract_deadlines_from_messages(
        messages,
        progress_callback=_progress,
    )

    print(f"\n  ✅ Found {len(deadlines)} potential deadline(s)")
    print(f"  {_hr()}")

    if not deadlines:
        print("  😴 No deadlines detected. The chat might be purely casual.")
        sys.exit(0)

    # ── 3. Resolve dates ─────────────────────────────────────────────────
    print("  📅 Resolving date phrases…")
    deadlines = resolve_deadlines(deadlines)
    resolved_count = sum(1 for d in deadlines if d.get("resolved_date"))
    print(f"  ✅ Resolved {resolved_count}/{len(deadlines)} date(s)")
    print(f"  {_hr()}")

    # ── 4. Deduplicate ───────────────────────────────────────────────────
    before = len(deadlines)
    deadlines = deduplicate_deadlines(deadlines)
    removed = before - len(deadlines)
    if removed:
        print(f"  🧹 Removed {removed} duplicate(s)")
    print(f"  📋 Final count: {len(deadlines)} deadline(s)")
    print(f"  {_hr()}")

    # ── 5. Display results ───────────────────────────────────────────────
    if args.json_output:
        # JSON output
        output = []
        for dl in deadlines:
            entry = {k: v for k, v in dl.items()}
            # Convert datetimes to ISO strings
            for key in ("resolved_date", "message_timestamp"):
                if isinstance(entry.get(key), datetime):
                    entry[key] = entry[key].isoformat()
            output.append(entry)
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        _print_table(deadlines)

    # ── 6. Export calendar ───────────────────────────────────────────────
    if not args.no_calendar:
        exportable = [d for d in deadlines if d.get("resolved_date")]
        if exportable:
            saved_path = save_calendar(exportable, output_path=args.output)
            print(f"  📆 Calendar saved → {saved_path}")
            print(f"     Import into Google Calendar / Apple Calendar / Outlook")
        else:
            print("  ⚠  No dates could be resolved — skipping calendar export.")

    print(f"\n  {_hr()}")
    print("  🎃 Happy Hacktoberfest! Stay on top of your deadlines. 🦥\n")


if __name__ == "__main__":
    main()
