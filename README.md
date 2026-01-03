# 🧠 DontForget: The AI Second Brain

**DontForget** is a local, "God Mode" memory engine for your terminal. It allows you to dump raw thoughts, tasks, and ideas into a database and retrieve them later using natural language, powered by Google Gemini AI and SQLite.

Unlike complex RAG systems that require vector databases and embeddings, DontForget uses a **"Lazy Storage, Brute-Force Retrieval"** architecture. It stores raw text with smart AI tags and uses SQLite's Full-Text Search (FTS5) to hunt down information, feeding the results back to the LLM for synthesis.

## ✨ Features

* **⚡ Zero-Friction Capture:** Just type `mem r "anything..."`. The AI automatically generates searchable tags and summaries.
* **🔍 "God Mode" Retrieval:** Ask questions like *"What tasks did I have for Project Cyoni last week?"*. The system uses fuzzy search + time-filtering + AI analysis to find the exact answer.
* **🛠️ Bulletproof Architecture:** Uses a single SQLite table with an FTS5 index. No sync issues, no complex vector math, no "missing ID" bugs.
* **📊 Cost-Aware:** Every response shows you the token usage and record count, so you know exactly how much "brain power" you used.
* **🔐 Private & Secure:** Your memories are stored locally in a SQLite database on your machine.
* **📝 Editor Support:** Automatically opens your system editor for long notes.

## 🚀 Installation

### 1. Prerequisites

* Python 3.10+
* A Google Gemini API Key (Free tier works great)

### 2. Quick Start

1.  **Install the tool:**
    ```bash
    # From the project directory
    pip install -e .
    ```

2.  **Add your API Key:**
    Create a `.env` file in `~/.dontforget/.env` (or in the current folder):
    ```ini
    GEMINI_API_KEY="your_gemini_api_key_here"
    ```

---

## 📖 Usage

### Remember (Input)

Dump anything. The AI will tag it concepts (e.g., "debt", "finance") rather than just words.

```bash
mem r "Paid 432 rs to Akash for dinner"
# 🧠 Saved! [Tags: finance, debt, akash, dinner]

mem r "Fix the login bug on Cyoni project"
# 🧠 Saved! [Tags: project-cyoni, bug, urgent]

```

**Pro Tip:** Type `mem r` without arguments to open your default editor (Vim, Notepad, etc.) for pasting long lists or code snippets.

### Remind (Query)

Ask naturally. You can filter by project, person, or time.

```bash
mem q "How much do I owe Akash?"
# Output: "You owe Akash 432 rs for dinner."

mem q "What are my pending tasks for Cyoni?"
# Output: "1. Fix login bug..."

```

### Delete (Forget)

Delete memories by describing them. The AI finds the best match.

```bash
mem d "That note about Akash"
# Output: "Deleted 1 item."

```

### Preview (List)

View all stored memories chronologically.

```bash
mem preview
# or
mem ls
```

---

## 🏗️ Architecture

**Standalone CLI:**
*   The `mem` command directly manages a local SQLite database (`~/.dontforget/memory.db`) and communicates with the Google Gemini API.
*   **Ingestion:** Text -> AI Tags -> SQLite (Raw + FTS Index).
*   **Retrieval:** Query -> AI Keywords -> SQLite FTS Search -> AI Synthesis.
*   No background server or complex setup required. Just install and run.

## 🛡️ Troubleshooting

*   **"GEMINI_API_KEY not found"**: Ensure your `.env` file is in the current directory or in `~/.dontforget/.env`.
*   **"Search Error"**: If the database schema gets corrupted, you can safely delete `~/.dontforget/memory.db`. It will be recreated on the next run.
*   **Command not found**: After running `pip install -e .`, you may need to restart your terminal or ensure your Python scripts folder is in your system's PATH.

---

**License:** GPL-3
**Author:** Suraj Kushwah
