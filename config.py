"""
Configuration constants for the Assignment & Deadline Extractor.
"""

# ── Ollama Model ──────────────────────────────────────────────────────────────
MODEL_NAME = "llama3.2:3b"

# ── Supported Chat Formats ────────────────────────────────────────────────────
SUPPORTED_CHAT_FORMATS = ["whatsapp", "telegram", "generic"]

# ── Date / Time Output Formats ────────────────────────────────────────────────
DATE_OUTPUT_FORMAT = "%d %b %Y"          # e.g. 25 Oct 2024
TIME_OUTPUT_FORMAT = "%I:%M %p"          # e.g. 05:00 PM
DATETIME_OUTPUT_FORMAT = "%d %b %Y, %I:%M %p"  # e.g. 25 Oct 2024, 05:00 PM

# ── Timezone ──────────────────────────────────────────────────────────────────
DEFAULT_TIMEZONE = "Asia/Kolkata"

# ── Extraction Settings ──────────────────────────────────────────────────────
MAX_RETRIES = 2            # JSON-parse retries per message
BATCH_CONTEXT_SIZE = 2     # Number of surrounding messages sent as context
