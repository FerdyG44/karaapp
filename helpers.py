import os
import sqlite3
from datetime import datetime

# DB path (aynı mantık app.py'de)
IS_PROD = os.environ.get("RENDER") == "true"
DB_PATH = "/var/data/data.db" if IS_PROD else "data.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def pick_lang(request):
    # basit: query param > session > default
    lang = None
    try:
        lang = request.args.get("lang")
    except Exception:
        lang = None
    if not lang:
        lang = "tr"
    if lang not in ("tr", "sv", "en"):
        lang = "tr"
    return lang

def currency_for_lang(lang):
    return {"tr": "TRY", "sv": "SEK", "en": "USD"}.get(lang, "USD")

def _parse_date(s):
    if not s:
        return None
    s = s.strip()
    try:
        # expecting YYYY-MM-DD
        datetime.strptime(s, "%Y-%m-%d")
        return s
    except Exception:
        return None

def _export_where_clause(show_all, user_id, start, end):
    clauses = []
    params = []
    if not show_all:
        clauses.append("r.user_id = ?")
        params.append(user_id)
    if start and end:
        clauses.append("r.day BETWEEN ? AND ?")
        params.extend([start, end])
    where_sql = "WHERE " + " AND ".join(clauses) if clauses else ""
    return where_sql, params
