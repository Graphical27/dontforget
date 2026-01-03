import sys
import os
import json
import sqlite3
import argparse
import datetime
import re
import subprocess
from pathlib import Path
from typing import List, Optional, Dict, Any

# Try to load .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from google import genai
    from google.genai import types
except ImportError:
    print("Error: 'google-genai' package is missing. Install it via pip.")
    sys.exit(1)

# --- CONFIGURATION ---
# We store data in ~/.dontforget/ by default
APP_DIR = Path.home() / ".dontforget"
DB_PATH = APP_DIR / "memory.db"
ENV_PATH = Path.cwd() / ".env" # Check current dir for .env first
APP_ENV_PATH = APP_DIR / ".env" # Check app dir

# Load env vars
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)
elif APP_ENV_PATH.exists():
    load_dotenv(APP_ENV_PATH)

GEMINI_KEY = os.getenv("GEMINI_API_KEY")
MODEL_ID = "gemini-2.5-flash" 

# --- COLORS ---
class Colors:
    GREEN = '\033[0;32m'
    BLUE = '\033[0;34m'
    YELLOW = '\033[1;33m'
    RED = '\033[0;31m'
    NC = '\033[0m'

    @staticmethod
    def print(text: str, color: str = NC, end: str = '\n'):
        if os.name == 'nt' and os.getenv('TERM') is None:
             pass
        print(f"{color}{text}{Colors.NC}", end=end)

# --- DATABASE ---
def init_db():
    if not APP_DIR.exists():
        APP_DIR.mkdir(parents=True, exist_ok=True)
        
    conn = sqlite3.connect(DB_PATH)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            raw_text TEXT,
            ai_tags TEXT
        );
    """)
    
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS memories_idx 
        USING fts5(raw_text, ai_tags, content='memories', content_rowid='id');
    """)

    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
          INSERT INTO memories_idx(rowid, raw_text, ai_tags) VALUES (new.id, new.raw_text, new.ai_tags);
        END;
    """)
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
          INSERT INTO memories_idx(memories_idx, rowid, raw_text, ai_tags) VALUES('delete', old.id, old.raw_text, old.ai_tags);
        END;
    """)
    
    conn.commit()
    conn.close()

def get_client():
    if not GEMINI_KEY:
        Colors.print("Error: GEMINI_API_KEY is not set.", Colors.RED)
        Colors.print(f"Please create a .env file in {Path.cwd()} or {APP_DIR} with GEMINI_API_KEY=...", Colors.YELLOW)
        sys.exit(1)
    return genai.Client(api_key=GEMINI_KEY)

def estimate_tokens(text: str) -> int:
    return len(str(text)) // 4

def execute_fuzzy_search(keywords: List[str]):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    clean_keys = [re.sub(r'[^a-zA-Z0-9]', '', k) for k in keywords if k]
    if not clean_keys: return []

    query_and = " AND ".join(f'"{k}"' for k in clean_keys)
    sql = f"SELECT rowid, * FROM memories_idx WHERE memories_idx MATCH ? ORDER BY rank LIMIT 30"
    
    rows = []
    try:
        cursor = conn.execute(sql, (query_and,))
        rows = [dict(row) for row in cursor.fetchall()]
    except:
        pass

    if len(rows) < 5:
        query_or = " OR ".join(f'"{k}"' for k in clean_keys)
        try:
            sql = f"SELECT rowid, * FROM memories_idx WHERE memories_idx MATCH ? ORDER BY rank LIMIT 30"
            cursor = conn.execute(sql, (query_or,))
            new_rows = [dict(row) for row in cursor.fetchall()]
            existing_ids = {r['rowid'] for r in rows}
            for nr in new_rows:
                if nr['rowid'] not in existing_ids:
                    rows.append(nr)
        except:
            pass

    final_results = []
    if rows:
        ids = [r['rowid'] for r in rows]
        id_list = ",".join(str(i) for i in ids)
        sql_full = f"SELECT id, raw_text, ai_tags, timestamp FROM memories WHERE id IN ({id_list})"
        cursor = conn.execute(sql_full)
        final_results = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return final_results

def delete_by_ids(ids: List[int]):
    conn = sqlite3.connect(DB_PATH)
    placeholders = ','.join('?' * len(ids))
    conn.execute(f"DELETE FROM memories WHERE id IN ({placeholders})", ids)
    conn.commit()
    conn.close()

def get_editor_input(initial_text: bytes = b"") -> str:
    editor = os.getenv("EDITOR")
    if not editor:
        if os.name == 'nt':
            editor = "notepad.exe"
        else:
            editor = "vim"
            
    import tempfile
    
    with tempfile.NamedTemporaryFile(suffix=".tmp", delete=False) as tf:
        tf.write(initial_text)
        tf_path = tf.name
    
    try:
        subprocess.call([editor, tf_path])
        with open(tf_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
    finally:
        if os.path.exists(tf_path):
            os.remove(tf_path)
            
    return content

# --- COMMANDS ---

ASCII_LOGO = f"""
{{Colors.BLUE}}   ___           _   {{Colors.YELLOW}}___                    _ 
{{Colors.BLUE}}  / _ \\___  _ __| |_ {{Colors.YELLOW}}| __|__ _ _ __ _ ___| |_ 
{{Colors.BLUE}} | (_) / _ \\| '_ \\  _{{Colors.YELLOW}}| _|/ _ \\ '_/ _` / -_)  _|
{{Colors.BLUE}}  \\___/\\___/|_|  \\__|{{Colors.YELLOW}}_|  \\___/_| \\__, \\___|\\__|
{{Colors.BLUE}}                     {{Colors.YELLOW}}           |___/          {{Colors.NC}}
""".format(Colors=Colors)

class RichArgumentParser(argparse.ArgumentParser):
    def print_help(self, file=None):
        if file is None:
            file = sys.stdout
        print(ASCII_LOGO, file=file)
        print(f"{Colors.GREEN}Your AI Second Brain for the Terminal{Colors.NC}\n", file=file)
        super().print_help(file)

def cmd_remember(args):
    content = " ".join(args.text)
    if not content:
        content = get_editor_input()
        if not content:
            Colors.print("Aborted (empty content).", Colors.RED)
            return

    client = get_client()
    Colors.print("🧠 Saving...", Colors.BLUE)
    
    try:
        prompt = f"""
        Generate 5 search tags for this thought.
        Input: "{content}"
        Format: JSON {{ "tags": ["tag1", "tag2"] }}
        """
        resp = client.models.generate_content(
            model=MODEL_ID, 
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        tags = json.loads(resp.text).get("tags", [])
        tags_str = ", ".join(tags)

        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT INTO memories (raw_text, ai_tags) VALUES (?, ?)", 
                (content, tags_str)
            )
            
        Colors.print("✔ Saved!", Colors.GREEN)
        Colors.print(f"Tags: {tags_str}", Colors.YELLOW)
        
    except Exception as e:
        Colors.print(f"Error: {e}", Colors.RED)

def cmd_remind(args):
    query = " ".join(args.query)
    if not query:
        Colors.print("Missing query.", Colors.RED)
        return

    client = get_client()
    Colors.print("🔍 Thinking...", Colors.BLUE)
    
    try:
        today = datetime.datetime.now().strftime("%Y-%m-%d %A")
        
        prompt_strat = f"""
        User Query: "{query}"
        Extract 3-5 keywords to search the database.
        Format: JSON {{ "keywords": ["word1", "word2"] }}
        """
        resp_strat = client.models.generate_content(
            model=MODEL_ID, 
            contents=prompt_strat,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        keywords = json.loads(resp_strat.text).get("keywords", [])
        # Colors.print(f"DEBUG: Keywords {keywords}", Colors.BLUE)

        rows = execute_fuzzy_search(keywords)
        
        context_str = ""
        for r in rows:
            context_str += f"[ID:{r['id']}] [{r['timestamp']}] {r['raw_text']}\n"

        token_count = estimate_tokens(context_str)
        if token_count > 6000: context_str = context_str[:24000] + "\n...[TRUNCATED]"

        final_prompt = f"""
        You are a Memory Assistant.
        Date: {today}
        User Query: "{query}"
        
        Relevant Memories:
        {context_str}
        
        Task: 
        1. Answer the question using ONLY the memories above.
        2. If asking for "Today" or "Last week", check the timestamps.
        3. If no relevant memories found, say "No relevant info found."
        """
        
        resp_final = client.models.generate_content(model=MODEL_ID, contents=final_prompt)
        
        print(f"\n{Colors.GREEN}{resp_final.text}{Colors.NC}\n")
        Colors.print("--------------------------------", Colors.BLUE)
        stats_str = f"{len(rows)} records | {token_count} tokens"
        Colors.print(f"📊 Stats: {stats_str}", Colors.YELLOW)
        print()
        
    except Exception as e:
        Colors.print(f"Error: {e}", Colors.RED)

def cmd_delete(args):
    query = " ".join(args.query)
    if not query:
        Colors.print("Missing query.", Colors.RED)
        return

    client = get_client()
    Colors.print("🔍 Finding to delete...", Colors.BLUE)
    
    try:
        keywords = query.split() # Simple split for delete is usually enough, or use AI
        rows = execute_fuzzy_search(keywords)
        
        if not rows: 
            Colors.print("No items found.", Colors.YELLOW)
            return

        context = "\n".join([f"ID:{r['id']} Text:{r['raw_text']}" for r in rows])
        prompt = f"""
        User wants to delete: "{query}"
        Which IDs match?
        Options:
        {context}
        Return JSON {{ "ids": [1] }} or {{ "ids": [] }}
        """
        resp = client.models.generate_content(
            model=MODEL_ID, 
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        ids = json.loads(resp.text).get("ids", [])
        
        if ids:
            delete_by_ids(ids)
            Colors.print(f"Deleted {len(ids)} items.", Colors.GREEN)
        else:
            Colors.print("Found items, but none matched exactly.", Colors.YELLOW)

    except Exception as e:
        Colors.print(f"Error: {e}", Colors.RED)

def cmd_preview(args):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute("SELECT * FROM memories ORDER BY timestamp DESC")
        rows = cursor.fetchall()
        
        if not rows:
            Colors.print("Database is empty.", Colors.YELLOW)
            return

        Colors.print(f"Found {len(rows)} memories:", Colors.BLUE)
        for row in rows:
            print(f"{Colors.YELLOW}[ID:{row['id']}] {Colors.BLUE}{row['timestamp']}{Colors.NC}")
            print(f"{row['raw_text']}")
            if row['ai_tags']:
                print(f"{Colors.GREEN}Tags: {row['ai_tags']}{Colors.NC}")
            print("-" * 40)
            
    except Exception as e:
        Colors.print(f"Error: {e}", Colors.RED)
    finally:
        conn.close()

def main():
    init_db()
    
    parser = RichArgumentParser(description="DontForget CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Remember
    p_rem = subparsers.add_parser("remember", aliases=['r', 'save'], help="Save a thought")
    p_rem.add_argument("text", nargs="*", help="Text to remember")
    p_rem.set_defaults(func=cmd_remember)

    # Remind
    p_ask = subparsers.add_parser("remind", aliases=['q', 'ask'], help="Ask a question")
    p_ask.add_argument("query", nargs="+", help="Question to ask")
    p_ask.set_defaults(func=cmd_remind)

    # Delete
    p_del = subparsers.add_parser("delete", aliases=['d'], help="Delete a memory")
    p_del.add_argument("query", nargs="+", help="Description to delete")
    p_del.set_defaults(func=cmd_delete)

    # Preview
    p_prev = subparsers.add_parser("preview", aliases=['p', 'list', 'ls'], help="List all memories")
    p_prev.set_defaults(func=cmd_preview)

    if len(sys.argv) < 2:
        parser.print_help()
        sys.exit(1)

    args = parser.parse_args()
    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
