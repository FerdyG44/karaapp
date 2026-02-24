import os
import sqlite3
from datetime import datetime
import secrets
import hashlib
from functools import wraps
from flask import request, Response
from flask import request, abort

# DB path (aynı mantık app.py'de)
IS_PROD = os.environ.get("RENDER") == "true"
DB_PATH = "/var/data/data.db" if IS_PROD else "data.db"

def generate_token(nbytes=32):
    """
    Rastgele okunabilir token üretir (URL-safe hex).
    nbytes=32 -> 64 hex karakterlik token.
    """
    return secrets.token_urlsafe(nbytes)

def hash_token(raw_token: str):
    """
    Token'ı veritabanında saklamak için hash'ler.
    SHA256 ile hash ve hex döndürür. (salt ekleyebilirsin.)
    """
    if raw_token is None:
        return None
    # basit SHA256; istersen HMAC + secret kullan
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

def _get_api_token_row(hashed_token):
    """
    Veritabanından token row'u getirir. (helpers.get_db() kullanılmalı)
    """
    from helpers import get_db  # eğer aynı dosyada değilse import uyarısı
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id, user_id, token, scopes, is_active, created_at FROM api_tokens WHERE token = ?",
            (hashed_token,)
        ).fetchone()
        return row
    finally:
        conn.close()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def _hash_token_plaintext(token: str) -> str:
    """Plain SHA256 hash for storing/comparing tokens.
    (Daha güvenli istersen salt ve HMAC kullan.)"""
    if token is None:
        return None
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def require_api_token(scopes_required=None):
    """
    Decorator: @require_api_token() veya @require_api_token(['records:read'])
    - Accepts Bearer header: Authorization: Bearer <token>
    - Falls back to ?api_key=<token> query param
    - Expects tokens stored in DB as hashed (sha256 of the raw token)
    - Sets request.api_user_id for use inside the route (keşke flask.g kullansaydık ama uyumluluk için)
    """
    if scopes_required is None:
        scopes_required = []

    # normalize to list
    if isinstance(scopes_required, (str,)):
        scopes_required = [scopes_required]


def generate_token(length=40) -> str:
    return secrets.token_urlsafe(length)  # güvenli random token

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

def _generate_api_token(nbytes=32):
    """
    Güvenli rastgele token üretir. token'ı kullanıcıya göstereceğiz (sadece bir kez).
    nbytes=32 -> token_urlsafe uzunluğu yeterli entropy sağlar.
    """
    return secrets.token_urlsafe(nbytes)

def _get_api_token_row(token):
    """
    DB'den token satırını döner veya None.
    """
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id, user_id, token, scopes, is_active FROM api_tokens WHERE token=? LIMIT 1",
            (token,)
        ).fetchone()
        return row
    finally:
        conn.close()

def api_auth_required(scopes_required=None):
    """
    API endpoint'lerini Bearer token ile korumak için dekoratör.
    usage: @api_auth_required(['records:read'])
    Eğer scopes_required None ise scope kontrolü atlanır.
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            # 1) get token from header or query
            auth = request.headers.get("Authorization", "")
            api_key = None
            if auth and auth.startswith("Bearer "):
                api_key = auth.split(" ", 1)[1].strip()
            else:
                api_key = request.args.get("api_key") or request.form.get("api_key")

            if not api_key:
                abort(401, description="Missing API token")

            hashed = _hash_token_plaintext(api_key)

            # 2) lookup token in DB
            conn = get_db()
            try:
                row = conn.execute(
                    "SELECT id, user_id, scopes, is_active FROM api_tokens WHERE token = ? LIMIT 1",
                    (hashed,),
                ).fetchone()
            finally:
                conn.close()

            if not row:
                abort(401, description="Invalid token")
            if row["is_active"] == 0:
                abort(401, description="Token revoked")

            # 3) check scopes
            token_scopes = set([s.strip() for s in (row["scopes"] or "").split(",") if s.strip()])
            required_scopes = set(scopes_required)
            if required_scopes and not required_scopes.issubset(token_scopes):
                abort(403, description="Insufficient scope")

            # 4) attach user id to request for route usage (backwards compat)
            try:
                # prefer request attribute (you used this earlier)
                request.api_user_id = row["user_id"]
            except Exception:
                # fallback: do nothing (route can still use DB to find user)
                pass

            return f(*args, **kwargs)
        return wrapped
    return decorator
