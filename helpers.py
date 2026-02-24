# helpers.py
import os
import sqlite3
import secrets
import hashlib
from datetime import datetime
from functools import wraps

from flask import request, abort, g, Response

# ----------------- Config / DB -----------------
IS_PROD = os.environ.get("RENDER") == "true"
DB_PATH = "/var/data/data.db" if IS_PROD else "data.db"

def get_db():
    """
    Basit sqlite bağlantısı. row_factory ile dict-benzeri erişim sağlar.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ----------------- Token helpers -----------------
def generate_token(nbytes=32):
    """
    Kullanıcıya gösterilecek ham token üretir.
    token_urlsafe döndürür (URL-safe).
    nbytes param: entropy miktarı.
    """
    return secrets.token_urlsafe(nbytes)

def _generate_api_token(nbytes=32):
    """
    İç kullanım / isim uyumluluğu: aynı işlevi döner.
    """
    return generate_token(nbytes)

def hash_token(raw_token: str):
    """
    Ham token'ı DB'de saklanacak forma çevirir.
    SHA-256 hex. (İstersen HMAC + secret ile geliştirebilirsin.)
    """
    if raw_token is None:
        return None
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

# DB helper: get token row by hashed token
def _get_api_token_row(hashed_token):
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id, user_id, token, scopes, is_active, created_at FROM api_tokens WHERE token = ? LIMIT 1",
            (hashed_token,)
        ).fetchone()
        return row
    finally:
        conn.close()

# Farklı adla çağrılabilecek helper (bazı kodlarda farklı isim kullanıldı)
def _get_api_token_row_plain(token_or_hashed):
    """
    Eğer kodun bir yerde ham token yerine hash bekliyorsa çağrılabilir.
    Burada kabul edilen arguman token ise hash'lenip DB'de aranır.
    """
    # normalize: eğer argüman uzunluğu 64 ve hex ise hash olduğu düşünülebilir,
    # ama güvenli davranış için her zaman hash'le arıyoruz.
    h = hash_token(token_or_hashed)
    return _get_api_token_row(h)

# ----------------- API auth decorator -----------------
def require_api_token(scopes_required=None):
    """
    Decorator factory: @require_api_token(scopes_required=["records:read"])
    - Accepts Bearer token in Authorization header OR api_key query param.
    - Veritabanında token hash'ini arar.
    - Eğer scopes_required verilmişse token.scopes ile karşılaştırır.
    - Başarılıysa request.api_user_id ve g.api_user_id atar.
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            # 1) token al: header (Bearer ...) öncelik, yoksa query param fallback
            auth = request.headers.get("Authorization", "") or ""
            api_key = None
            if auth.startswith("Bearer "):
                api_key = auth.split(" ", 1)[1].strip()
            else:
                api_key = (request.args.get("api_key") or request.form.get("api_key") or "").strip()

            if not api_key:
                abort(401, description="Missing API token")

            # 2) hash ve DB lookup
            hashed = hash_token(api_key)
            row = _get_api_token_row(hashed)
            if not row:
                abort(401, description="Invalid API token")
            if row["is_active"] == 0:
                abort(401, description="Token revoked")

            # 3) scope kontrolü (varsa)
            if scopes_required:
                token_scopes = set([s.strip() for s in (row["scopes"] or "").split(",") if s.strip()])
                required_scopes = set(scopes_required if isinstance(scopes_required, (list,tuple)) else [scopes_required])
                if not required_scopes.issubset(token_scopes):
                    abort(403, description="Insufficient scope")

            # 4) attach user id for route usage
            try:
                request.api_user_id = row["user_id"]
                g.api_user_id = row["user_id"]
            except Exception:
                # nadiren request nesnesine atama başarısız olursa yinede devam et
                pass

            return f(*args, **kwargs)
        return wrapped
    return decorator

# backward-compatible alias (eğer app kodu bu ismi kullanıyorsa)
api_auth_required = require_api_token

# ----------------- Localization & utility -----------------
def pick_lang(req):
    """
    Basit dil seçici: query param > default 'tr'.
    (Eğer session veya kullanıcı tercihleri varsa genişlet.)
    """
    try:
        lang = req.args.get("lang")
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