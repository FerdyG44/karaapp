import os
import sqlite3
import secrets
import hashlib
from functools import wraps
from datetime import datetime
from flask import request, abort, g

# ---------- Config ----------
IS_PROD = os.environ.get("RENDER") == "true"
DB_PATH = "/var/data/data.db" if IS_PROD else "data.db"

# ---------- DB helper ----------
def get_db():
    """Return a sqlite3 connection with row_factory set to Row."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ---------- Token utilities ----------
def generate_token(nbytes: int = 32) -> str:
    """
    Generate a URL-safe random token to show to the user.
    nbytes=32 gives a reasonably long token.
    """
    return secrets.token_urlsafe(nbytes)

def _generate_api_token(nbytes: int = 32) -> str:
    """Alias: güvenli token üretimi (kullanıcıya gösterilecek raw token)."""
    return generate_token(nbytes)

def hash_token(raw_token: str) -> str | None:
    """Hash a raw token for storage/lookup (SHA256 hex). Returns hex string or None if input None."""
    if raw_token is None:
        return None
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

def _get_api_token_row_by_hashed(hashed_token: str):
    """
    Return api_tokens row by hashed token (the value stored in DB).
    Returns sqlite3.Row or None.
    """
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id, user_id, token, scopes, is_active, created_at FROM api_tokens WHERE token = ? LIMIT 1",
            (hashed_token,)
        ).fetchone()
        return row
    finally:
        conn.close()

def get_api_token_row_from_raw(raw_token: str):
    """Convenience: hash raw token and fetch DB row."""
    h = hash_token(raw_token)
    return _get_api_token_row_by_hashed(h)

# ---------- API auth decorators ----------
def require_api_token(scopes_required=None):
    """
    Decorator factory that enforces presence of a valid API token (Bearer or api_key query param).
    Usage:
      @require_api_token(scopes_required=["records:read"])
      def route(...): ...
    On success, sets request.api_user_id and g.api_user_id (if g available).
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            # 1) read token
            auth = request.headers.get("Authorization", "")
            api_key = None
            if auth and auth.startswith("Bearer "):
                api_key = auth.split(" ", 1)[1].strip()
            else:
                api_key = request.args.get("api_key") or request.form.get("api_key")

            if not api_key:
                abort(401, "Missing API token")

            # 2) lookup token (we store hashed tokens in DB)
            hashed = hash_token(api_key)
            if not hashed:
                abort(401, "Invalid API token")

            conn = get_db()
            try:
                row = conn.execute(
                    "SELECT id, user_id, scopes, is_active FROM api_tokens WHERE token = ? LIMIT 1",
                    (hashed,)
                ).fetchone()
            finally:
                conn.close()

            if not row:
                abort(401, "Invalid API token")
            if row["is_active"] == 0:
                abort(401, "Token revoked")

            # 3) scope check (if requested)
            if scopes_required:
                token_scopes = set([s.strip() for s in (row["scopes"] or "").split(",") if s.strip()])
                required = set(scopes_required if isinstance(scopes_required, (list, tuple)) else [scopes_required])
                if not required.issubset(token_scopes):
                    abort(403, "Insufficient scope")

            # 4) attach user id for route usage
            try:
                request.api_user_id = row["user_id"]
            except Exception:
                pass
            try:
                g.api_user_id = row["user_id"]
            except Exception:
                pass

            return f(*args, **kwargs)
        return wrapped
    return decorator

# Backwards-compatible alias (if başka kod api_auth_required kullanıyorsa)
def api_auth_required(scopes_required=None):
    return require_api_token(scopes_required=scopes_required)

# ---------- i18n / misc helpers ----------
def pick_lang(request):
    """
    Simple language picker: query param > default 'tr'
    Accepts only 'tr', 'sv', 'en'.
    """
    try:
        lang = request.args.get("lang")
    except Exception:
        lang = None
    if not lang:
        lang = "tr"
    if lang not in ("tr", "sv", "en"):
        lang = "tr"
    return lang

def currency_for_lang(lang: str) -> str:
    return {"tr": "TRY", "sv": "SEK", "en": "USD"}.get(lang, "USD")

def _parse_date(s: str):
    if not s:
        return None
    s = s.strip()
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return s
    except Exception:
        return None

def _export_where_clause(show_all, user_id, start, end):
    """
    Helper to create WHERE clause fragments for exports.
    Returns (where_sql, params_list)
    """
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

# ---------- end of helpers.py ----------