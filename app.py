"""
🦥 Deadline Extractor — Streamlit Web App
==========================================
Extract assignment deadlines from group chat exports.
Runs 100% locally — your messages never leave your machine.
"""

import json
import csv
import io
import tempfile
from datetime import datetime, timedelta

import streamlit as st
import pandas as pd

from chat_parser import parse_chat
from extractor import extract_deadlines_from_messages
from date_resolver import resolve_date, resolve_deadlines
from deduplicator import deduplicate_deadlines
from calendar_export import create_calendar
import config

# ── Demo chat embedded directly ──────────────────────────────────────────────
DEMO_CHAT = """\
25/10/23, 9:15 am - Prof. Sharma: Good morning class. Submit your DBMS assignment by Friday 5pm. Topic: ER diagrams for library management system.
25/10/23, 9:16 am - Rahul: Which assignment sir? The one from last week?
25/10/23, 9:17 am - Prof. Sharma: No, this is a new one. Check the LMS for details.
25/10/23, 9:30 am - Priya: Guys has anyone started the ML lab report? It's due on Monday
25/10/23, 10:45 am - Amit: 😂😂 bro I haven't even attended the last 3 lectures
25/10/23, 11:00 am - Priya: Amit tu toh gaya 💀
25/10/23, 2:15 pm - CR Neha: IMPORTANT: CN viva is on 28th October, Saturday. Prepare chapters 1-4 from Kurose.
25/10/23, 2:16 am - Amit: Saturday ko bhi viva? 😭
25/10/23, 2:17 pm - Rahul: Bhai padh le ab
25/10/23, 3:00 pm - Prof. Sharma: Also, the DBMS mid-sem project proposal is due by November 1st. Groups of 3-4 students.
25/10/23, 4:30 pm - Sneha: Has anyone submitted the OS assignment? The one on process scheduling?
25/10/23, 4:31 pm - Priya: Yeah that was due yesterday
25/10/23, 4:32 pm - Sneha: Oh no 😱
25/10/23, 6:00 pm - CR Neha: Update: Prof said DBMS assignment deadline extended to Sunday 8pm instead of Friday
25/10/23, 6:01 pm - Rahul: Finally some good news 🙌
25/10/23, 8:00 pm - Amit: Anyone up for cricket tomorrow?
25/10/23, 9:30 pm - Priya: Reminder - ML lab report format: PDF only, max 10 pages, submit on LMS before Monday 11:59pm\
"""

# ── Page configuration ───────────────────────────────────────────────────────
st.set_page_config(
    page_title="🦥 Deadline Extractor",
    page_icon="🦥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    /* ── Global tweaks ─────────────────────────────────────── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* Main container padding */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }

    /* ── Sidebar styling ──────────────────────────────────── */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1A1D23 0%, #0E1117 100%);
    }

    [data-testid="stSidebar"] .stMarkdown h1 {
        background: linear-gradient(135deg, #FF6B35, #FFB347);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 1.8rem;
        font-weight: 700;
    }

    /* ── Metric cards ─────────────────────────────────────── */
    [data-testid="stMetric"] {
        background: #1A1D23;
        border: 1px solid #2D3139;
        border-radius: 12px;
        padding: 1rem 1.2rem;
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    [data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        border-color: #FF6B35;
    }
    [data-testid="stMetric"] label {
        color: #9CA3AF !important;
        font-weight: 500;
    }
    [data-testid="stMetric"] [data-testid="stMetricValue"] {
        font-size: 2rem;
        font-weight: 700;
        color: #FAFAFA;
    }

    /* ── Tabs ─────────────────────────────────────────────── */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.5rem;
        background: #1A1D23;
        border-radius: 12px;
        padding: 0.35rem;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        padding: 0.6rem 1.4rem;
        font-weight: 600;
        color: #9CA3AF;
    }
    .stTabs [aria-selected="true"] {
        background: #FF6B35 !important;
        color: #fff !important;
    }

    /* ── Buttons ──────────────────────────────────────────── */
    .stButton > button[kind="primary"],
    .stButton > button[data-testid="stBaseButton-primary"] {
        background: linear-gradient(135deg, #FF6B35, #FF8F5E);
        border: none;
        border-radius: 10px;
        font-weight: 600;
        padding: 0.6rem 2rem;
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }
    .stButton > button[kind="primary"]:hover,
    .stButton > button[data-testid="stBaseButton-primary"]:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 14px rgba(255, 107, 53, 0.35);
    }

    /* ── Download buttons ─────────────────────────────────── */
    .stDownloadButton > button {
        background: #1A1D23;
        border: 1px solid #2D3139;
        border-radius: 10px;
        font-weight: 500;
        transition: border-color 0.2s ease;
    }
    .stDownloadButton > button:hover {
        border-color: #FF6B35;
    }

    /* ── Urgency badges ───────────────────────────────────── */
    .urgency-high   { color: #FF4B4B; font-weight: 700; }
    .urgency-medium { color: #FBBF24; font-weight: 600; }
    .urgency-low    { color: #34D399; font-weight: 500; }
    .overdue-badge  { color: #FF4B4B; font-weight: 700; text-transform: uppercase; }

    /* ── Footer ───────────────────────────────────────────── */
    .footer {
        text-align: center;
        color: #6B7280;
        font-size: 0.82rem;
        padding: 2.5rem 0 1rem;
        border-top: 1px solid #2D3139;
        margin-top: 3rem;
    }

    /* ── File uploader ────────────────────────────────────── */
    [data-testid="stFileUploader"] {
        border: 2px dashed #2D3139;
        border-radius: 12px;
        padding: 1rem;
    }

    /* ── Expander ─────────────────────────────────────────── */
    [data-testid="stExpander"] {
        border: 1px solid #2D3139;
        border-radius: 10px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ── Helper utilities ─────────────────────────────────────────────────────────

def _time_left(due: datetime | None) -> str:
    """Return a human-readable string for time remaining until *due*."""
    if due is None:
        return "—"
    now = datetime.now()
    delta = due - now
    if delta.total_seconds() < 0:
        return "OVERDUE"
    days = delta.days
    hours = delta.seconds // 3600
    parts: list[str] = []
    if days:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours or not parts:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    return " ".join(parts)


def _urgency_html(urgency: str) -> str:
    """Wrap urgency text in a coloured span."""
    level = urgency.lower() if urgency else "low"
    css_class = f"urgency-{level}" if level in ("high", "medium", "low") else "urgency-low"
    return f'<span class="{css_class}">{urgency.upper()}</span>'


def _time_left_html(text: str) -> str:
    """Colour the *time left* string when overdue."""
    if text == "OVERDUE":
        return '<span class="overdue-badge">OVERDUE</span>'
    return text


def _build_display_df(deadlines: list[dict]) -> pd.DataFrame:
    """Convert raw deadline dicts into a display-ready DataFrame."""
    rows = []
    for d in deadlines:
        resolved = d.get("resolved_date")
        if not resolved:
            ref_date = d.get("message_timestamp") or datetime.now()
            if isinstance(ref_date, str):
                try:
                    ref_date = datetime.fromisoformat(ref_date)
                except (ValueError, TypeError):
                    ref_date = datetime.now()
            resolved = resolve_date(d.get("date_phrase", ""), ref_date)

        time_left = _time_left(resolved)

        rows.append(
            {
                "Task": d.get("task", "—"),
                "Subject": d.get("subject", "—"),
                "Due Date": resolved.strftime("%a, %d %b %Y %I:%M %p") if resolved else d.get("date_phrase", "—"),
                "Time Left": time_left,
                "Posted By": d.get("posted_by") or d.get("author", "—"),
                "Urgency": d.get("urgency", "low"),
                "_raw_due": resolved,
            }
        )
    return pd.DataFrame(rows)


def _summary_metrics(df: pd.DataFrame) -> None:
    """Render st.metric cards for total, upcoming-this-week, and overdue."""
    total = len(df)
    overdue = int((df["Time Left"] == "OVERDUE").sum())
    now = datetime.now()
    week_end = now + timedelta(days=7)
    upcoming = 0
    for _, row in df.iterrows():
        due = row.get("_raw_due")
        if due is not None and now <= due <= week_end:
            upcoming += 1

    cols = st.columns(3)
    with cols[0]:
        st.metric("📌 Total Deadlines", total)
    with cols[1]:
        st.metric("📅 Upcoming (7 days)", upcoming)
    with cols[2]:
        st.metric("🚨 Overdue", overdue)


def _render_results_table(df: pd.DataFrame) -> None:
    """Render a styled HTML table of deadlines."""
    if df.empty:
        st.info("No deadlines found.")
        return

    # Build HTML table
    header = (
        "<table style='width:100%; border-collapse:collapse; font-size:0.95rem;'>"
        "<thead><tr style='border-bottom:2px solid #2D3139; text-align:left;'>"
        "<th style='padding:10px;'>Task</th>"
        "<th style='padding:10px;'>Subject</th>"
        "<th style='padding:10px;'>Due Date</th>"
        "<th style='padding:10px;'>Time Left</th>"
        "<th style='padding:10px;'>Posted By</th>"
        "<th style='padding:10px;'>Urgency</th>"
        "</tr></thead><tbody>"
    )
    body_rows = []
    for _, row in df.iterrows():
        body_rows.append(
            "<tr style='border-bottom:1px solid #1F2937;'>"
            f"<td style='padding:10px;'>{row['Task']}</td>"
            f"<td style='padding:10px;'>{row['Subject']}</td>"
            f"<td style='padding:10px;'>{row['Due Date']}</td>"
            f"<td style='padding:10px;'>{_time_left_html(row['Time Left'])}</td>"
            f"<td style='padding:10px;'>{row['Posted By']}</td>"
            f"<td style='padding:10px;'>{_urgency_html(row['Urgency'])}</td>"
            "</tr>"
        )
    table_html = header + "".join(body_rows) + "</tbody></table>"
    st.markdown(table_html, unsafe_allow_html=True)


def _download_buttons(deadlines: list[dict], df: pd.DataFrame, reminder_minutes: int) -> None:
    """Render download buttons for ICS, JSON, and CSV."""
    cols = st.columns(3)

    # ── ICS ───────────────────────────────────────────────
    with cols[0]:
        ics_string = create_calendar(deadlines)
        st.download_button(
            label="📅 Download Calendar (.ics)",
            data=ics_string,
            file_name="deadlines.ics",
            mime="text/calendar",
            use_container_width=True,
        )

    # ── JSON ──────────────────────────────────────────────
    with cols[1]:
        # Serialise datetimes to ISO strings for JSON
        json_safe = []
        for d in deadlines:
            entry = {}
            for k, v in d.items():
                if isinstance(v, datetime):
                    entry[k] = v.isoformat()
                else:
                    entry[k] = v
            json_safe.append(entry)
        json_bytes = json.dumps(json_safe, indent=2, ensure_ascii=False).encode("utf-8")
        st.download_button(
            label="📊 Download as JSON",
            data=json_bytes,
            file_name="deadlines.json",
            mime="application/json",
            use_container_width=True,
        )

    # ── CSV ───────────────────────────────────────────────
    with cols[2]:
        display_df = df.drop(columns=["_raw_due"], errors="ignore")
        csv_buffer = io.StringIO()
        display_df.to_csv(csv_buffer, index=False)
        st.download_button(
            label="📄 Download as CSV",
            data=csv_buffer.getvalue().encode("utf-8"),
            file_name="deadlines.csv",
            mime="text/csv",
            use_container_width=True,
        )


def _process_chat(text: str, chat_format: str, model_name: str) -> list[dict]:
    """Run the full extraction pipeline on raw chat text.

    Returns the deduplicated deadline list and stores it in session state.
    """
    if model_name:
        config.MODEL_NAME = model_name

    progress = st.progress(0, text="⏳ Parsing chat messages…")

    # Save text to a temp file so chat_parser can read it
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as tmp:
        tmp.write(text)
        tmp_path = tmp.name

    fmt = chat_format.lower().replace("-", "").replace(" ", "_")
    if fmt == "auto_detect" or fmt == "autodetect" or fmt == "auto":
        fmt = "auto"

    messages = parse_chat(tmp_path, fmt)
    total_msgs = len(messages)
    progress.progress(10, text=f"✅ Parsed {total_msgs} messages")

    def _cb(curr, tot):
        pct = 10 + int((curr / tot) * 65)
        progress.progress(pct, text=f"🤖 Analyzing message {curr}/{tot} with {config.MODEL_NAME}…")

    raw_deadlines = extract_deadlines_from_messages(messages, progress_callback=_cb)
    progress.progress(80, text=f"🔍 Found {len(raw_deadlines)} potential deadline(s). Resolving dates…")

    resolved_deadlines = resolve_deadlines(raw_deadlines)
    progress.progress(90, text="🧹 Deduplicating and merging updates…")

    deadlines = deduplicate_deadlines(resolved_deadlines)
    progress.progress(100, text=f"✅ Done — {len(deadlines)} deadlines extracted!")

    return deadlines


# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("# 🦥 Deadline Extractor")
    st.caption(
        "Extract assignment deadlines from your group chats.\n\n"
        "Runs **100 % locally** — your messages never leave your machine."
    )
    st.divider()

    model_name = st.text_input("🤖 Ollama model", value=config.MODEL_NAME)
    chat_format = st.selectbox(
        "💬 Chat format",
        ["Auto-detect", "WhatsApp", "Telegram", "Generic"],
    )
    reminder_minutes = st.select_slider(
        "⏰ Calendar reminder (minutes before)",
        options=[15, 30, 60, 120],
        value=30,
    )

    st.divider()
    with st.expander("ℹ️ About this app"):
        st.markdown(
            """
            **Built for Hacktoberfest 2024** — Week 3: *"Slow and Steady"* 🦥

            - Uses **open-weight models** via [Ollama](https://ollama.com)
            - Runs **entirely offline** — no cloud APIs, no telemetry
            - **No data leaves your machine** — ever

            Made with ❤️ by students, for students.
            """
        )


# ── Main area ────────────────────────────────────────────────────────────────

tab_upload, tab_results, tab_demo = st.tabs(["📤 Upload Chat", "📋 Results", "🧪 Try Demo"])

# ── Tab 1: Upload Chat ───────────────────────────────────────────────────────
with tab_upload:
    st.subheader("Upload or paste your chat export")

    uploaded_file = st.file_uploader(
        "Drop a chat export file here",
        type=["txt", "zip"],
        help="WhatsApp: Settings → Chats → Export Chat → Without Media",
    )

    st.markdown("**— or —**")
    pasted_text = st.text_area(
        "Paste chat messages directly",
        height=220,
        placeholder="25/10/23, 9:15 am - Prof. Sharma: Submit your DBMS assignment by Friday 5pm…",
    )

    if st.button("🚀 Extract Deadlines", type="primary", use_container_width=True):
        # Determine source text
        source_text = None
        if uploaded_file is not None:
            raw_bytes = uploaded_file.read()
            # Handle zip files
            if uploaded_file.name.endswith(".zip"):
                import zipfile
                with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
                    # Find the first .txt inside the zip
                    txt_files = [n for n in zf.namelist() if n.endswith(".txt")]
                    if txt_files:
                        source_text = zf.read(txt_files[0]).decode("utf-8", errors="replace")
                    else:
                        st.error("No .txt file found inside the ZIP archive.")
            else:
                source_text = raw_bytes.decode("utf-8", errors="replace")
        elif pasted_text.strip():
            source_text = pasted_text.strip()

        if source_text:
            try:
                deadlines = _process_chat(source_text, chat_format, model_name)
                st.session_state["deadlines"] = deadlines
                st.session_state["display_df"] = _build_display_df(deadlines)
                st.success(f"🎉 Extracted **{len(deadlines)}** deadline(s). Switch to the **📋 Results** tab to view them!")
            except Exception as exc:
                st.error(f"Something went wrong: {exc}")
        else:
            st.warning("Please upload a file or paste some chat messages first.")

# ── Tab 2: Results ───────────────────────────────────────────────────────────
with tab_results:
    if "deadlines" not in st.session_state or not st.session_state["deadlines"]:
        st.info("No deadlines extracted yet. Head over to **📤 Upload Chat** or **🧪 Try Demo** first.")
    else:
        deadlines = st.session_state["deadlines"]
        df = st.session_state["display_df"]

        _summary_metrics(df)
        st.markdown("")  # spacing
        _render_results_table(df)
        st.markdown("")  # spacing
        _download_buttons(deadlines, df, reminder_minutes)

# ── Tab 3: Try Demo ──────────────────────────────────────────────────────────
with tab_demo:
    st.subheader("🧪 Try with sample data")
    st.caption("Pre-loaded with a realistic college WhatsApp group chat. Click the button to see the extractor in action!")

    with st.expander("👀 Preview sample chat", expanded=False):
        st.code(DEMO_CHAT, language=None)

    if st.button("▶️ Run Demo", type="primary", use_container_width=True):
        try:
            deadlines = _process_chat(DEMO_CHAT, "WhatsApp", model_name)
            st.session_state["deadlines"] = deadlines
            st.session_state["display_df"] = _build_display_df(deadlines)

            df = st.session_state["display_df"]
            _summary_metrics(df)
            st.markdown("")
            _render_results_table(df)
            st.markdown("")
            _download_buttons(deadlines, df, reminder_minutes)
        except Exception as exc:
            st.error(f"Something went wrong: {exc}")

# ── Footer ───────────────────────────────────────────────────────────────────
st.markdown(
    '<div class="footer">Built with ❤️ and 🦥 energy for Hacktoberfest | Powered by Ollama + Llama 3.2</div>',
    unsafe_allow_html=True,
)
