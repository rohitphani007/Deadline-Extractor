# 🦥 Deadline Extractor

### Stop scrolling through 500 messages. Let the sloth do it.

[![Hacktoberfest 2024](https://img.shields.io/badge/Hacktoberfest-2024-orange?style=for-the-badge&logo=hacktoberfest)](https://hacktoberfest.com)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)
[![Runs Locally](https://img.shields.io/badge/Runs-100%25_Locally-purple?style=for-the-badge&logo=ollama&logoColor=white)]()

---

## 😩 The Problem

Every student knows the pain. Your class WhatsApp group has 500+ unread messages, and somewhere in the avalanche of memes, random polls, and "who has the notes?" threads, the class rep posted an assignment deadline — **three days ago**. You only find out when your friend casually asks, "Did you submit the compiler design assignment?" and your stomach drops. That dreaded *"Wait, THAT was due today?!"* moment hits different at 11:47 PM.

Class reps shouldn't have to be human reminder bots. Students shouldn't have to archaeologically dig through chat histories to find what's due. There has to be a better way.

## 💡 The Solution

**Deadline Extractor** takes your exported chat file, runs it through a **local open-weight AI model**, and produces:

- 📋 A **clean, sorted table** of all assignment deadlines
- 📅 An **`.ics` calendar file** you can import into Google Calendar / Apple Calendar / Outlook / any calendar app
- 🔒 **No internet required.** No data leaves your machine. **No API costs. Ever.**

Just export your group chat, point the tool at it, and never miss a deadline again.

## 📸 Demo

![Demo](assets/demo.png)

> *Screenshot coming soon — the sloth is still rendering it.*

---

## ✨ Features

- 🔒 **100% Local & Private** — Your messages never leave your machine. Period.
- 🌐 **Works Offline** — No internet needed after the one-time model download.
- 💰 **Free Forever** — No API keys, no subscriptions, no usage limits.
- 📱 **WhatsApp Export Support** — The most common format for student groups, ready out of the box.
- 📅 **Calendar Export** — `.ics` files work with Google Calendar, Apple Calendar, Outlook, and more.
- 🔄 **Smart Deduplication** — Handles "deadline extended to..." updates without creating duplicates.
- 🧠 **Powered by Llama 3.2** — Open-weight model that runs on a regular laptop. No GPU required.
- 🎨 **Beautiful Web UI** — Streamlit-powered dashboard for a point-and-click experience.

---

## 🚀 Quick Start

```bash
# 1. Install Ollama (https://ollama.com)
# 2. Pull the model
ollama pull llama3.2:3b

# 3. Clone and setup
git clone https://github.com/YOUR_USERNAME/deadline-extractor.git
cd deadline-extractor
pip install -r requirements.txt

# 4a. Run the CLI
python cli.py your_chat.txt

# 4b. Or launch the web UI
streamlit run app.py
```

---

## 📲 How to Export Your WhatsApp Chat

Getting your chat file is easy — it takes about 30 seconds:

1. **Open** the group chat in WhatsApp
2. **Tap** ⋮ (three dots in the top right) → **More** → **Export chat**
3. **Choose** "Without media" (we only need the text)
4. **Save** the `.txt` file to your computer

That's it! Feed this `.txt` file to the Deadline Extractor and let the sloth do its thing.

---

## ⚙️ How It Works

1. **Parse** — The chat file is split into structured messages with timestamps, authors, and content using regex-based parsing.
2. **Extract** — Each message is analyzed by a local LLM (Llama 3.2 via Ollama) to identify anything that looks like a deadline or assignment.
3. **Resolve** — Relative dates like "Friday", "next week", or "tomorrow" are converted to absolute dates using the message timestamp as a reference point.
4. **Deduplicate** — Repeated and updated deadlines are merged intelligently. If someone says "deadline extended to Monday", the old date is replaced.
5. **Export** — Results are displayed as a clean sorted table and exported to an `.ics` calendar file.

### Architecture

```
Chat Export (.txt)
    │
    ▼
┌──────────────┐
│  Chat Parser │  ← Regex-based, supports WhatsApp/Telegram
└──────┬───────┘
       │ [{timestamp, author, text}, ...]
       ▼
┌──────────────┐
│  Extractor   │  ← Ollama + Llama 3.2 (local inference)
└──────┬───────┘
       │ [{task, date_phrase, subject}, ...]
       ▼
┌──────────────┐
│ Date Resolver│  ← dateparser library
└──────┬───────┘
       │ [{task, due_date, subject}, ...]
       ▼
┌──────────────┐
│ Deduplicator │  ← Fuzzy matching + update detection
└──────┬───────┘
       │
       ▼
┌──────────────┐     ┌──────────┐
│  CLI Output  │     │ .ics File│
│  (table)     │     │ (calendar)│
└──────────────┘     └──────────┘
```

---

## 🔓 Why Open-Source AI Matters Here

Group chats contain some of the most personal conversations in your digital life. Your frustrations about a tough exam, your friend venting about a professor, inside jokes, personal plans — it's all in there. Sending that to a cloud API means your private messages, your friends' messages, and your professors' messages all land on someone else's server. Even with the best privacy policies, you're trusting a third party with conversations that were never meant to leave the group. That's not a trade-off students should have to make just to track their homework.

**Running everything locally means ZERO data leaves your machine.** The AI model lives on your hard drive. The chat file is read from your disk and processed in memory. No network calls, no telemetry, no logs on a remote server. This is the kind of task where open-weight models aren't just "nice to have" — they're the **only responsible choice**.

It also means the tool is **truly free**. A student who can't afford API credits — and let's be honest, most students are watching every dollar — can still use it without worrying about rate limits or surprise bills. It works on a train, in a hostel with spotty WiFi, in a library basement with no signal. Anywhere your laptop goes, your deadline tracker goes with it. And because it's open-weight, you can swap models (Mistral, Gemma, Phi) without changing a single line of code. You can even fine-tune for your specific language mix — Hindi-English, Spanglish, Franglais — whatever your group chat speaks.

---

## 🛠️ Tech Stack

| Component | Technology |
|---|---|
| AI Model | Llama 3.2 3B (via Ollama) |
| Language | Python 3.10+ |
| Chat Parsing | Regex + datetime |
| Date Resolution | dateparser |
| Calendar Export | ics library |
| Web UI | Streamlit |
| CLI | argparse |

---

## 💻 CLI Usage

```bash
# Basic usage — extract deadlines and print to console
python cli.py chat.txt

# Export deadlines to an .ics calendar file
python cli.py chat.txt --output deadlines.ics

# Use a different model
python cli.py chat.txt --model mistral:7b

# Set a custom Ollama host
python cli.py chat.txt --host http://localhost:11434

# Verbose output for debugging
python cli.py chat.txt --verbose

# Combine options
python cli.py chat.txt --output deadlines.ics --model llama3.2:3b --verbose
```

---

## 🤝 Contributing

Contributions are welcome! Whether it's fixing a bug, adding a feature, or improving the docs — every bit helps.

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes (`git commit -m 'Add amazing feature'`)
4. **Push** to the branch (`git push origin feature/amazing-feature`)
5. **Open** a Pull Request

### Ideas for Contributions

- Support for more chat formats (Telegram, Discord, iMessage)
- Multi-language deadline detection
- Recurring deadline support
- Desktop notifications integration
- Better date resolution for ambiguous phrases

Please make sure to update tests as appropriate and follow the existing code style.

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- [**Hacktoberfest 2024**](https://hacktoberfest.com) & [**DEV Community**](https://dev.to) — Week 3: *Slow and Steady* 🦥
- [**Meta's Llama 3.2**](https://ai.meta.com/llama/) — Open-weight model that makes local AI accessible
- [**Ollama**](https://ollama.com) — Making it dead simple to run LLMs locally
- **International Sloth Day** 🦥 — The spiritual inspiration for this project

---

<p align="center">
  Made with 🦥 energy — slow, steady, and never missing a deadline again.
</p>
