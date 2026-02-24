# ---------- app.py: cleaned imports and app init ----------
import os
import re
import sqlite3
import threading
import time
import csv
import secrets
import hashlib
import logging

from datetime import datetime, timedelta
from functools import wraps
from collections import defaultdict

from flask import (
    Flask, request, jsonify, render_template, redirect,
    url_for, flash, abort, session, g, Response
)
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import generate_password_hash, check_password_hash

from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    login_required, current_user
)
from flask_wtf.csrf import CSRFProtect, CSRFError

import stripe

# local helpers (single import)
import helpers
from helpers import get_db, pick_lang, currency_for_lang

# ---------- logging ----------
# configure basic logging; app.logger will be available after app created
logging.basicConfig(level=logging.INFO)

# ---------- stripe key (env) ----------
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")

# ---------------- App ----------------
app = Flask(__name__)

# Proxy arkasında doğru https/host algısı
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

IS_PROD = (os.environ.get("RENDER") == "true") or (os.environ.get("FLASK_ENV") == "production")

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=IS_PROD,
)

csrf = CSRFProtect(app)

@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    # basit redirect; burada pick_lang kullanmıyoruz çünkü hata oluştu
    from flask import request, redirect, url_for, flash
    flash("CSRF error. Refresh and try again.", "error")
    return redirect(request.referrer or url_for("login", lang="tr"))

# ---------------- Config ----------------

DATA_DIR = os.getenv("DATA_DIR", "data")
os.makedirs(DATA_DIR, exist_ok=True)

IS_PROD = os.environ.get("RENDER") == "true"

DB_PATH = "/var/data/data.db" if IS_PROD else "data.db"

SUPPORTED_LANGS = ["tr", "sv", "en"]

def get_port():
    try:
        return int(os.environ.get("PORT", "5000"))
    except Exception:
        return 5000
    
# ---------------- I18N ----------------
I18N = {
    "tr": {
        "title": "KarApp",
        "subtitle": "Günlük satış ve gider gir, kârını anında gör.",
        "welcome": "Hoşgeldin",

        "login_title": "Giriş",
        "username": "Kullanıcı adı",
        "password": "Şifre",
        "login": "Giriş",
        "logout": "Çıkış",
        "login_error": "Hatalı giriş",
        "need_username_password": "Kullanıcı adı ve şifre gerekli",

        "sales": "Satış",
        "expense": "Gider",
        "profit": "Kâr",
        "date": "Tarih",
        "save": "Kaydet",
        "profit_note": "Not: Kâr otomatik = satış - gider",

        "new_record": "Yeni kayıt",
        "records_title": "Kayıtlar (son 50)",
        "daily_chart_title": "30 Günlük Grafik",
        "monthly_chart_title": "Aylık Grafik",

        "total_sales": "Toplam satış",
        "total_expense": "Toplam gider",
        "total_profit": "Toplam kâr",

        "admin_users": "Kullanıcıları yönet",
        "manage_users": "Kullanıcıları yönet",
        "all_records": "Tüm kayıtlar",

        "username_exists": "Bu kullanıcı adı zaten var",
        "user_created": "Kullanıcı oluşturuldu",
        "user_deleted": "Kullanıcı silindi",
        "cannot_delete_self": "Kendini silemezsin",

        "expires_days": "Kaç gün geçerli? (0 = süresiz)",
        "is_admin": "Admin mi?",
        "create": "Oluştur",
        "delete": "Sil",
        "expires_at": "Bitiş",
        "role": "Rol",
        "admin": "Admin",
        "user": "Kullanıcı",
        "expired": "Süre dolmuş kullanıcı",

        "actions": "İşlem",

        "edit_record": "Kayıt Düzenle",
        "edit_subtitle": "Kaydı güncelle ve kaydet.",
        "back": "Geri",

        "invalid_amount": "Tutarlar negatif olamaz",
        "invalid_date": "Tarih formatı geçersiz",
        "too_large": "Tutar çok büyük",
        "too_many_attempts": "Çok fazla deneme yapıldı. Lütfen daha sonra tekrar deneyin.",

        "unlock": "Kilidi kaldır",
        "unlock_ok": "Kullanıcının giriş kilidi kaldırıldı.",
        
        "export_csv": "CSV indir",
        "export_all_csv": "Tüm kayıtlar CSV",

        "date_from": "Başlangıç",
        "date_to": "Bitiş",
        "download_csv": "CSV İndir",

        
        "monthly_desc": "Aylık abonelik (iptal edilebilir)",
        "yearly_desc": "Yıllık abonelik (daha uygun)",
        "choose_plan": "Plan seç",
        "go_pro": "Pro’ya geç",
        "pro_subscription_title": "Pro Abonelik",
        "pro_subscription_desc": "CSV/Excel indirme gibi Pro özellikler için abonelik başlat.",
        "billing_note": "Ödeme Stripe üzerinden güvenli şekilde alınır.",
        "monthly": "Aylık",
        "yearly": "Yıllık",
        "back": "Geri",

        "settings": "Ayarlar",
        "settings_title": "Ayarlar",
        "default_range": "Varsayılan Aralık",
        "default_range_desc": "Dashboard açıldığında otomatik seçilecek tarih aralığı.",
        "range_all": "Tümü",
        "range_30": "Son 30 gün",
        "range_90": "Son 90 gün",
        "range_365": "Son 365 gün",
        "save": "Kaydet",
        "updated": "Güncellendi",

        "account": "Hesabım",
        "settings": "Ayarlar",
        "settings_desc": "Görünüm ve varsayılan tercihlerini ayarla.",
        "currency": "Para birimi",
        "default_range": "Varsayılan Aralık",
        "back": "Geri",
        "save": "Kaydet",
        "all": "Tümü",
        "logout": "Çıkış",
        "manage_users": "Kullanıcıları yönet",
        "all_records": "Tüm kayıtlar",
        
        "account": "Hesabım",
        "username": "Kullanıcı adı",
        "plan": "Plan",
        "expires": "Bitiş",
        "export_access": "Export erişimi",
        "open": "Açık",
        "closed": "Kapalı",
        "back": "Geri",
        "enabled": "Açık",
        "settings": "Ayarlar",
        "expires_at": "Bitiş",

        "today_sales": "Bugünkü satış",
        "today_expense": "Bugünkü gider",
        "today_profit": "Bugünkü kâr",
        

        "lang_tr": "Türkçe",
        "lang_sv": "Svenska",
        "lang_en": "English",
    },

    "sv": {
        "title": "VinstApp",
        "subtitle": "Ange dagens försäljning och kostnader och se vinsten direkt.",
        "welcome": "Välkommen",

        "login_title": "Logga in",
        "username": "Användarnamn",
        "password": "Lösenord",
        "login": "Logga in",
        "logout": "Logga ut",
        "login_error": "Fel inloggning",
        "need_username_password": "Användarnamn och lösenord krävs",

        "sales": "Försäljning",
        "expense": "Kostnad",
        "profit": "Vinst",
        "date": "Datum",
        "save": "Spara",
        "profit_note": "Not: Vinst automatiskt = försäljning - kostnad",

        "new_record": "Ny post",
        "records_title": "Poster (senaste 50)",
        "daily_chart_title": "30-dagars graf",
        "monthly_chart_title": "Månadsgraf",

        "total_sales": "Total försäljning",
        "total_expense": "Total kostnad",
        "total_profit": "Total vinst",

        "admin_users": "Hantera användare",
        "manage_users": "Hantera användare",
        "all_records": "Alla poster",

        "username_exists": "Användarnamnet finns redan",
        "user_created": "Användare skapad",
        "user_deleted": "Användare borttagen",
        "cannot_delete_self": "Du kan inte ta bort dig själv",

        "expires_days": "Giltig i dagar? (0 = obegränsad)",
        "is_admin": "Admin?",
        "create": "Skapa",
        "delete": "Ta bort",
        "expires_at": "Utgång",
        "role": "Roll",
        "admin": "Admin",
        "user": "Användare",
        "expired": "Utgången användare",

        "actions": "Åtgärd",

        "edit_record": "Redigera post",
        "edit_subtitle": "Uppdatera posten och spara.",
        "back": "Tillbaka",

        "invalid_amount": "Belopp kan inte vara negativa",
        "invalid_date": "Ogiltigt datumformat",
        "too_large": "Beloppet är för stort",
        "too_many_attempts": "För många försök. Försök igen senare.",

        "unlock": "Lås upp",
        "unlock_ok": "Inloggningslåset är borttaget.",

        "export_csv": "Ladda ner CSV",
        "export_all_csv": "Alla poster (CSV)", 

        "date_from": "Från datum",
        "date_to": "Till datum",
        "download_csv": "Ladda ner CSV", 

        
        "monthly_desc": "Månadsabonnemang (kan avslutas när som helst)",
        "yearly_desc": "Årsabonnemang (bäst pris)",
        "choose_plan": "Välj plan",
        "go_pro": "Skaffa Pro",
        "pro_subscription_title": "Pro-abonnemang",
        "pro_subscription_desc": "Starta en prenumeration för Pro-funktioner som CSV/Excel-export.",
        "billing_note": "Betalningen hanteras säkert via Stripe.",
        "monthly": "Månadsvis",
        "yearly": "Årsvis",
        "back": "Tillbaka",

        "settings": "Inställningar",
        "settings_title": "Inställningar",
        "default_range": "Standardintervall",
        "default_range_desc": "Datumintervall som väljs automatiskt när dashboarden öppnas.",
        "range_all": "Alla",
        "range_30": "Senaste 30 dagar",
        "range_90": "Senaste 90 dagar",
        "range_365": "Senaste 365 dagar",
        "save": "Spara",
        "updated": "Uppdaterad",

        "account": "Konto",
        "settings": "Inställningar",
        "settings_desc": "Justera dina inställningar och standardval.",
        "currency": "Valuta",
        "default_range": "Standardintervall",
        "back": "Tillbaka",
        "save": "Spara",
        "all": "Alla",
        "logout": "Logga ut",
        "manage_users": "Hantera användare",
        "all_records": "Alla poster",
        
        "account": "Konto",
        "username": "Användarnamn",
        "plan": "Plan",
        "expires": "Gäller till",
        "export_access": "Exportåtkomst",
        "open": "Öppen",
        "closed": "Stängd",
        "back": "Tillbaka",
        "disabled": "Stängd",
        "expires": "Gäller till",
        "settings": "Inställningar",
        "expires_at": "Gäller till",

        "today_sales": "Dagens försäljning",
        "today_expense": "Dagens kostnad",
        "today_profit": "Dagens vinst",

        "lang_tr": "Türkçe",
        "lang_sv": "Svenska",
        "lang_en": "English",
    },

    "en": {
        "title": "ProfitApp",
        "subtitle": "Enter daily sales and expenses and see profit instantly.",
        "welcome": "Welcome",

        "login_title": "Login",
        "username": "Username",
        "password": "Password",
        "login": "Login",
        "logout": "Logout",
        "login_error": "Invalid login",
        "need_username_password": "Username and password required",

        "sales": "Sales",
        "expense": "Expense",
        "profit": "Profit",
        "date": "Date",
        "save": "Save",
        "profit_note": "Note: Profit = sales - expense",

        "new_record": "New record",
        "records_title": "Records (last 50)",
        "daily_chart_title": "Last 30 days",
        "monthly_chart_title": "Monthly chart",

        "total_sales": "Total sales",
        "total_expense": "Total expense",
        "total_profit": "Total profit",

        "admin_users": "Manage users",
        "manage_users": "Manage users",
        "all_records": "All records",

        "username_exists": "Username already exists",
        "user_created": "User created",
        "user_deleted": "User deleted",
        "cannot_delete_self": "You cannot delete yourself",

        "expires_days": "Valid for days? (0 = unlimited)",
        "is_admin": "Admin?",
        "create": "Create",
        "delete": "Delete",
        "expires_at": "Expires",
        "role": "Role",
        "admin": "Admin",
        "user": "User",
        "expired": "Expired user",

        "actions": "Actions",

        "edit_record": "Edit record",
        "edit_subtitle": "Update the record and save.",
        "back": "Back",

        "invalid_amount": "Amounts cannot be negative",
        "invalid_date": "Invalid date format",
        "too_large": "Amount is too large",
        "too_many_attempts": "Too many attempts. Try later.",

        "unlock": "Unlock",
        "unlock_ok": "Login lock cleared.",

        "export_csv": "Download CSV",
        "export_all_csv": "All records (CSV)",

        "date_from": "From date",
        "date_to": "To date",
        "download_csv": "Download CSV",
        
        
        "monthly_desc": "Monthly subscription (cancel anytime)",
        "yearly_desc": "Yearly subscription (best value)",
        "choose_plan": "Choose a plan",
        "go_pro": "Go Pro",
        "pro_subscription_title": "Pro Subscription",
        "pro_subscription_desc": "Start a subscription to unlock Pro features like CSV/Excel export.",
        "billing_note": "Payment is securely processed by Stripe.",
        "monthly": "Monthly",
        "yearly": "Yearly",
        "back": "Back",

        "settings": "Settings",
        "settings_title": "Settings",
        "default_range": "Default Range",
        "default_range_desc": "Date range that is selected automatically when the dashboard opens.",
        "range_all": "All",
        "range_30": "Last 30 days",
        "range_90": "Last 90 days",
        "range_365": "Last 365 days",
        "save": "Save",
        "updated": "Updated",

        "account": "Account",
        "settings": "Settings",
        "settings_desc": "Adjust your preferences and defaults.",
        "currency": "Currency",
        "default_range": "Default range",
        "back": "Back",
        "save": "Save",
        "all": "All",
        "logout": "Logout",
        "manage_users": "Manage users",
        "all_records": "All records",

        "account": "Account",
        "username": "Username",
        "plan": "Plan",
        "expires": "Expires",
        "export_access": "Export access",
        "open": "Open",
        "closed": "Closed",
        "back": "Back",
        "settings": "Settings", 
        "enabled": "Enabled",
        "disabled": "Disabled",
        "expires": "Expires",
        "expires_at": "Expires",

        "today_sales": "Today's sales",
        "today_expense": "Today's expense",
        "today_profit": "Today's profit",

        "lang_tr": "Türkçe",
        "lang_sv": "Svenska",
        "lang_en": "English",
    },
}


# ---------------- Helpers ----------------
def currency_for_lang(lang: str) -> str:
    if lang == "sv":
        return "kr"
    if lang == "en":
        return "$"
    return "₺"


def pick_lang(req) -> str:
    # 1) explicit ?lang=xx
    q = (req.args.get("lang") or "").lower().strip()
    if q in SUPPORTED_LANGS:
        session["lang"] = q
        return q

    # 2) session
    s = (session.get("lang") or "").lower().strip()
    if s in SUPPORTED_LANGS:
        return s

    # 3) browser
    header = (req.headers.get("Accept-Language") or "").lower()
    for code in ["sv", "en", "tr"]:
        if code in header:
            session["lang"] = code
            return code

    session["lang"] = "tr"
    return "tr"


def parse_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def is_valid_date_yyyy_mm_dd(day: str) -> bool:
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", day or ""):
        return False
    y, m, d = day.split("-")
    y, m, d = int(y), int(m), int(d)
    return 1900 <= y <= 2100 and 1 <= m <= 12 and 1 <= d <= 31

def create_api_token(user_id: int, token: str, name: str = None, scopes: str = ""):
    conn = get_db()
    try:
        conn.execute("INSERT INTO api_tokens (user_id, token, name, scopes) VALUES (?, ?, ?, ?)",
                     (user_id, token, name, scopes))
        conn.commit()
    finally:
        conn.close()

def list_integrations(user_id: int):
    conn = get_db()
    try:
        return conn.execute("SELECT * FROM integrations WHERE user_id = ?", (user_id,)).fetchall()
    finally:
        conn.close()

def add_import_job(user_id: int, filename: str):
    conn = get_db()
    try:
        conn.execute("INSERT INTO import_jobs (user_id, filename, status) VALUES (?, ?, 'pending')",
                     (user_id, filename))
        conn.commit()
    finally:
        conn.close()

_login_attempts = defaultdict(list)  # key -> [timestamps]
MAX_ATTEMPTS = 8
WINDOW_SECONDS = 10 * 60   # 10 dk
LOCK_SECONDS = 15 * 60     # 15 dk
_login_locked_until = {}   # key -> unix time

# ---------------- DB helpers ----------------
def get_db():
    # DB_PATH'in klasörünü garanti et
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
         os.makedirs(db_dir, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """
    Initialize DB schema and run safe (idempotent) migrations.
    Call this at app startup (ensure DB_PATH dir exists before).
    """
    conn = get_db()
    try:
        # ensure foreign keys
        conn.execute("PRAGMA foreign_keys = ON;")

        # ----- core tables -----
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_admin INTEGER NOT NULL DEFAULT 0,
                expires_at TEXT,
                plan TEXT DEFAULT 'free'
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                day TEXT NOT NULL,
                sales REAL NOT NULL,
                expense REAL NOT NULL,
                profit REAL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
            )
        """)

        # ----- optional / new columns for users -----
        # helper to safely add column only if missing
        def add_column_if_missing(table, column_sql, colname):
            cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
            if colname not in cols:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column_sql}")

        # users: currency, default_range_days, stripe fields, stripe ids, subscription_status
        add_column_if_missing("users", "plan TEXT DEFAULT 'free'", "plan")  # already included in CREATE, safe
        add_column_if_missing("users", "currency TEXT", "currency")
        add_column_if_missing("users", "default_range_days INTEGER DEFAULT 30", "default_range_days")
        add_column_if_missing("users", "stripe_customer_id TEXT", "stripe_customer_id")
        add_column_if_missing("users", "stripe_subscription_id TEXT", "stripe_subscription_id")
        add_column_if_missing("users", "subscription_status TEXT", "subscription_status")
        add_column_if_missing("users", "expires_at TEXT", "expires_at")  # included in CREATE but safe

        # records: profit and user_id handled in CREATE, but also ensure migrations for old dbs
        add_column_if_missing("records", "profit REAL", "profit")
        add_column_if_missing("records", "user_id INTEGER", "user_id")

        # ----- new feature tables -----
        conn.execute("""
            CREATE TABLE IF NOT EXISTS api_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token TEXT NOT NULL,
                name TEXT,
                scopes TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS integrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                provider TEXT NOT NULL,
                config TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS import_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                filename TEXT,
                status TEXT DEFAULT 'pending',
                errors TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # ----- lightweight migrations/repairs for historic DBs -----
        # If profit column is NULL for existing records, compute it.
        try:
            conn.execute("UPDATE records SET profit = (COALESCE(sales,0) - COALESCE(expense,0)) WHERE profit IS NULL")
        except Exception:
            # ignore if records table empty or other issue
            pass

        # If user_id in records is NULL, try to attach to first user (if any)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(records)").fetchall()]
        if "user_id" in cols:
            has_nulls = conn.execute("SELECT COUNT(1) as c FROM records WHERE user_id IS NULL").fetchone()["c"]
            if has_nulls:
                admin = conn.execute("SELECT id FROM users ORDER BY id ASC LIMIT 1").fetchone()
                admin_id = admin["id"] if admin else None
                if admin_id:
                    conn.execute("UPDATE records SET user_id = ? WHERE user_id IS NULL", (admin_id,))

        # ----- ensure at least one admin user exists (if no users exist yet) -----
        r = conn.execute("SELECT COUNT(1) as c FROM users").fetchone()
        if r and r["c"] == 0:
            # create default admin (change password after first login)
            pw = generate_password_hash("admin123")
            conn.execute("INSERT INTO users (username, password_hash, is_admin, plan) VALUES (?, ?, ?, ?)",
                         ("admin", pw, 1, "pro"))
            # note: create more secure random password in prod and show it once

        conn.commit()
    finally:
        conn.close()
        

_db_inited = False
_db_lock = threading.Lock()

def ensure_admin_from_env_once():

    flag = os.environ.get("ADMIN_CREATE_ON_START", "").lower() == "true"
    if not flag:
        return

    username = (os.environ.get("ADMIN_USERNAME") or "").strip()
    password = (os.environ.get("ADMIN_PASSWORD") or "").strip()
    
    if not username or not password:
        print("ADMIN env missing (ADMIN_USERNAME/ADMIN_PASSWORD)", flush=True)
        return

    conn = get_db()
    try:
        # ENV admin kullanıcı var mı?
        u = conn.execute(
            "SELECT id FROM users WHERE username = ? LIMIT 1",
            (username,),
        ).fetchone()

        if not u:
            # yoksa oluştur (şifreyi burada set eder)
            conn.execute(
                "INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, 1)",
                (username, generate_password_hash(password)),
            )
            conn.commit()
            env_admin_id = conn.execute(
                "SELECT id FROM users WHERE username = ? LIMIT 1",
                (username,),
            ).fetchone()["id"]
            print(f"Admin created from env: {username}", flush=True)
        else:
            env_admin_id = u["id"]
            # varsa admin yap ama şifreyi asla değiştirme
            conn.execute("UPDATE users SET is_admin = 1 WHERE id = ?", (env_admin_id,))
            conn.commit()
            print(f"Admin ensured from env (no password change): {username}", flush=True)

        # diğer tüm adminleri düşür (tek admin ENV admin kalsın)
        conn.execute(
            "UPDATE users SET is_admin = 0 WHERE id != ? AND is_admin = 1",
            (env_admin_id,),
        )
        conn.commit()
        print("Other admins demoted. Only ENV admin remains.", flush=True)

    finally:
        conn.close()

def ensure_db():
    global _db_inited
    if _db_inited:
        return
    with _db_lock:
        if _db_inited:
            return
        init_db()
        ensure_admin_from_env_once()
        _db_inited = True

# ✅ Ensure DB + initial admin even when running under gunicorn (Render)
try:
    ensure_db()   # burada init_db + ensure_admin_from_env_once zaten var
except Exception as e:
    print("Startup init error:", e, flush=True)

@app.before_request
def _ensure_db_before_request():
    ensure_db()


# ---------------- Auth (Flask-Login) ----------------
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


class User(UserMixin):
    def __init__(self, id, username, password_hash, is_admin=0, expires_at=None, plan="free",
                 currency="SEK", default_range_days=30):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.is_admin = is_admin
        self.expires_at = expires_at
        self.plan = plan or "free"
        self.currency = currency or "SEK"
        self.default_range_days = default_range_days if default_range_days is not None else 30
        
    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        try:
            dt = datetime.fromisoformat(self.expires_at)
            return datetime.utcnow() > dt
        except Exception:
            return False


def get_user_by_id(user_id: int):
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return User(row) if row else None
    finally:
        conn.close()


def get_user_by_id(user_id: int):
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id, username, password_hash, is_admin, expires_at, plan, currency, default_range_days FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()

    if not row:
        return None

    return User(
        id=row["id"],
        username=row["username"],
        password_hash=row["password_hash"],
        is_admin=row["is_admin"],
        expires_at=row["expires_at"],
        plan=row["plan"],
        currency=row["currency"],
        default_range_days=row["default_range_days"],
    )

def get_user_by_username(username):
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id, username, password_hash, is_admin, expires_at, plan FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    finally:
        conn.close()

    if not row:
        return None

    return User(
        id=row["id"],
        username=row["username"],
        password_hash=row["password_hash"],
        is_admin=row["is_admin"],
        expires_at=row["expires_at"],
        plan=row["plan"],
    )

@login_manager.user_loader
def load_user(user_id):
    try:
        u = get_user_by_id(int(user_id))
        # auto-logout if expired
        if u and u.is_expired():
            return None
        return u
    except Exception:
        return None


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)
        if not getattr(current_user, "is_admin", False):
            abort(403)
        return fn(*args, **kwargs)
    return wrapper


# ---------------- Routes: auth ----------------
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

@app.get("/login")
def login():
    lang = pick_lang(request)
    t = I18N.get(lang, I18N["tr"])
    return render_template("login.html", lang=lang, t=t)

@app.post("/login")
def login_post():
    lang = pick_lang(request)
    t = I18N.get(lang, I18N["tr"])

    now = time.time()

    username = (request.form.get("username") or "").strip()
    password = (request.form.get("password") or "").strip()

    # username boşsa throttle yapma, direkt hata
    if not username or not password:
        flash(t.get("need_username_password"), "error")
        return redirect(url_for("login", lang=lang))

    key = username.strip().lower()  # boşluk + case güvenli

    locked_until = _login_locked_until.get(key, 0)
    if now < locked_until:
        flash(t.get("too_many_attempts", "Too many attempts. Try later."), "error")
        return redirect(url_for("login", lang=lang))

    user = get_user_by_username(username)
    if not user or not check_password_hash(user.password_hash, password):
        ts = _login_attempts[key]
        ts.append(now)
        ts[:] = [x for x in ts if now - x <= WINDOW_SECONDS]
        if len(ts) >= MAX_ATTEMPTS:
            _login_locked_until[key] = now + LOCK_SECONDS

        flash(t.get("login_error"), "error")
        return redirect(url_for("login", lang=lang))

    if user.is_expired():
        flash(t.get("expired", "Expired user"), "error")
        return redirect(url_for("login", lang=lang))

    login_user(user)

    # başarılı login -> kilidi temizle
    _login_attempts.pop(key, None)
    _login_locked_until.pop(key, None)

    # ---- NEXT + LANG FIX (MUTLAKA FONKSİYON İÇİNDE) ----
    nxt = request.args.get("next")
    if not nxt:
        return redirect(url_for("index", lang=lang))

    # güvenlik: sadece relative URL
    p = urlparse(nxt)
    if p.scheme or p.netloc:
        return redirect(url_for("index", lang=lang))

    qs = parse_qs(p.query)
    if "lang" not in qs:
        qs["lang"] = [lang]

    fixed = urlunparse(("", "", p.path or "/", p.params, urlencode(qs, doseq=True), p.fragment))
    return redirect(fixed)

@app.get("/logout")
@login_required
def logout():
    lang = pick_lang(request)
    logout_user()
    return redirect(url_for("login", lang=lang))


# ---------------- Routes: index ----------------
@app.get("/")
@login_required
def index():
    lang = pick_lang(request)
    t = I18N.get(lang, I18N["tr"])
    currency = getattr(current_user, "currency", None) or currency_for_lang(lang)

    show_all = (request.args.get("all") == "1") and getattr(current_user, "is_admin", False)

    # --- Range filtresi + user default ---
    selected_range = (request.args.get("range") or "").strip()
    if selected_range == "":
        dr = getattr(current_user, "default_range_days", 30) or 0
        selected_range = "" if dr == 0 else str(dr)
    range_days = selected_range

    start = None
    end = None
    if range_days.isdigit():
        d = int(range_days)
        if d > 0:
            start = (datetime.now() - timedelta(days=d)).strftime("%Y-%m-%d")
            end = datetime.now().strftime("%Y-%m-%d")

    conn = get_db()
    try:
        # --- Today summary (user-specific) ---
        today = datetime.now().strftime("%Y-%m-%d")
        try:
            # Eğer users tablonda row factory kullanıyorsan dict tarzı sonuç gelir; değilse index ile kullan
            today_row = conn.execute(
                """
                SELECT
                    COALESCE(SUM(sales),0) AS s,
                    COALESCE(SUM(expense),0) AS e,
                    COALESCE(SUM(profit),0) AS p
                FROM records
                WHERE user_id = ? AND day = ?
                """,
                (int(current_user.id), today)
            ).fetchone()
        except Exception:
            # boşsa sıfırla
            today_row = {"s": 0, "e": 0, "p": 0}

        today_sales = float((today_row["s"] if isinstance(today_row, dict) else today_row[0]) or 0)
        today_expense = float((today_row["e"] if isinstance(today_row, dict) else today_row[1]) or 0)
        today_profit = float((today_row["p"] if isinstance(today_row, dict) else today_row[2]) or 0)

        # --- Asıl veri sorguları (show_all / user) ---
        if show_all:
            if start and end:
                rows = conn.execute(
                    """
                    SELECT r.id, r.day, r.sales, r.expense, r.profit, u.username
                    FROM records r
                    JOIN users u ON u.id = r.user_id
                    WHERE r.day BETWEEN ? AND ?
                    ORDER BY r.day DESC, r.id DESC
                    LIMIT 50
                    """,
                    (start, end)
                ).fetchall()

                totals = conn.execute(
                    """
                    SELECT
                        COALESCE(SUM(r.sales),0) AS s,
                        COALESCE(SUM(r.expense),0) AS e,
                        COALESCE(SUM(r.profit),0) AS p
                    FROM records r
                    WHERE r.day BETWEEN ? AND ?
                    """,
                    (start, end)
                ).fetchone()
            else:
                rows = conn.execute(
                    """
                    SELECT r.id, r.day, r.sales, r.expense, r.profit, u.username
                    FROM records r
                    JOIN users u ON u.id = r.user_id
                    ORDER BY r.day DESC, r.id DESC
                    LIMIT 50
                    """
                ).fetchall()

                totals = conn.execute(
                    """
                    SELECT
                        COALESCE(SUM(r.sales),0) AS s,
                        COALESCE(SUM(r.expense),0) AS e,
                        COALESCE(SUM(r.profit),0) AS p
                    FROM records r
                    """
                ).fetchone()

            daily_raw = conn.execute(
                """
                SELECT day,
                       SUM(sales) AS sales,
                       SUM(expense) AS expense,
                       SUM(profit) AS profit
                FROM records
                GROUP BY day
                ORDER BY day DESC
                LIMIT 30
                """
            ).fetchall()

            monthly_raw = conn.execute(
                """
                SELECT SUBSTR(day, 1, 7) AS month,
                       SUM(sales) AS sales,
                       SUM(expense) AS expense,
                       SUM(profit) AS profit
                FROM records
                GROUP BY SUBSTR(day, 1, 7)
                ORDER BY month ASC
                """
            ).fetchall()

        else:
            if start and end:
                rows = conn.execute(
                    """
                    SELECT id, day, sales, expense, profit
                    FROM records
                    WHERE user_id = ? AND day BETWEEN ? AND ?
                    ORDER BY day DESC, id DESC
                    LIMIT 50
                    """,
                    (int(current_user.id), start, end)
                ).fetchall()

                totals = conn.execute(
                    """
                    SELECT
                        COALESCE(SUM(sales),0) AS s,
                        COALESCE(SUM(expense),0) AS e,
                        COALESCE(SUM(profit),0) AS p
                    FROM records
                    WHERE user_id = ? AND day BETWEEN ? AND ?
                    """,
                    (int(current_user.id), start, end)
                ).fetchone()
            else:
                rows = conn.execute(
                    """
                    SELECT id, day, sales, expense, profit
                    FROM records
                    WHERE user_id = ?
                    ORDER BY day DESC, id DESC
                    LIMIT 50
                    """,
                    (int(current_user.id),)
                ).fetchall()

                totals = conn.execute(
                    """
                    SELECT
                        COALESCE(SUM(sales),0) AS s,
                        COALESCE(SUM(expense),0) AS e,
                        COALESCE(SUM(profit),0) AS p
                    FROM records
                    WHERE user_id = ?
                    """,
                    (int(current_user.id),)
                ).fetchone()

            daily_raw = conn.execute(
                """
                SELECT day,
                       SUM(sales) AS sales,
                       SUM(expense) AS expense,
                       SUM(profit) AS profit
                FROM records
                WHERE user_id = ?
                GROUP BY day
                ORDER BY day DESC
                LIMIT 30
                """,
                (int(current_user.id),)
            ).fetchall()

            monthly_raw = conn.execute(
                """
                SELECT SUBSTR(day, 1, 7) AS month,
                       SUM(sales) AS sales,
                       SUM(expense) AS expense,
                       SUM(profit) AS profit
                FROM records
                WHERE user_id = ?
                GROUP BY SUBSTR(day, 1, 7)
                ORDER BY month ASC
                """,
                (int(current_user.id),)
            ).fetchall()

        total_sales = float(totals["s"] or 0)
        total_expense = float(totals["e"] or 0)
        total_profit = float(totals["p"] or 0)

        daily_rows = [dict(r) for r in reversed(daily_raw)]
        monthly_rows = [dict(r) for r in monthly_raw]

        return render_template(
            "index.html",
            lang=lang,
            t=t,
            currency=currency,
            show_all=show_all,
            rows=rows,
            daily_rows=daily_rows,
            monthly_rows=monthly_rows,
            total_sales=round(total_sales, 2),
            total_expense=round(total_expense, 2),
            total_profit=round(total_profit, 2),

            today_sales=round(today_sales, 2),
            today_expense=round(today_expense, 2),
            today_profit=round(today_profit, 2),
            today_date=today,

            start=start,
            end=end,
            range_days=range_days,
            selected_range=selected_range
        )

    finally:
        conn.close()

@app.post("/records")
@login_required
def index_post():
    lang = pick_lang(request)
    t = I18N.get(lang, I18N["tr"])

    day = (request.form.get("day") or "").strip()
    sales = parse_float(request.form.get("sales"), 0)
    expense = parse_float(request.form.get("expense"), 0)

    # ---- plan limit: free max 100 records ----
    if getattr(current_user, "plan", "free") == "free":
        conn = get_db()
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM records WHERE user_id = ?",
                (int(current_user.id),)
            ).fetchone()[0]
        finally:
            conn.close()

        if count >= 100:
            flash("Free plan limit reached (100 records). Upgrade to Pro.", "error")
            return redirect(url_for("index", lang=lang))

    # ---- validations ----
    if not is_valid_date_yyyy_mm_dd(day):
        flash(t.get("invalid_date"), "error")
        return redirect(url_for("index", lang=lang))

    if sales < 0 or expense < 0:
        flash(t.get("invalid_amount"), "error")
        return redirect(url_for("index", lang=lang))

    if sales > 1e9 or expense > 1e9:
        flash(t.get("too_large"), "error")
        return redirect(url_for("index", lang=lang))

    profit = sales - expense

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO records (user_id, day, sales, expense, profit) VALUES (?, ?, ?, ?, ?)",
            (int(current_user.id), day, sales, expense, profit),
        )
        conn.commit()
    finally:
        conn.close()

    return redirect(url_for("index", lang=lang))

@app.post("/records/<int:record_id>/delete")
@login_required
def delete_record(record_id):
    lang = pick_lang(request)

    conn = get_db()
    try:
        owner = conn.execute("SELECT user_id FROM records WHERE id = ?", (record_id,)).fetchone()
        if not owner:
            abort(404)

        if not getattr(current_user, "is_admin", False) and int(owner["user_id"]) != int(current_user.id):
            abort(403)

        conn.execute("DELETE FROM records WHERE id = ?", (record_id,))
        conn.commit()
    finally:
        conn.close()

    return redirect(url_for("index", lang=lang))


@app.route("/records/<int:record_id>/edit", methods=["GET", "POST"])
@login_required
def edit_record(record_id):
    lang = pick_lang(request)
    t = I18N.get(lang, I18N["tr"])
    currency = currency_for_lang(lang)

    conn = get_db()
    try:
        rec = conn.execute(
            "SELECT id, day, sales, expense, profit, user_id FROM records WHERE id = ?",
            (record_id,),
        ).fetchone()

        if not rec:
            abort(404)

        if not getattr(current_user, "is_admin", False) and int(rec["user_id"]) != int(current_user.id):
            abort(403)

        if request.method == "POST":
            day = (request.form.get("day") or "").strip()
            sales = parse_float(request.form.get("sales"), 0)
            expense = parse_float(request.form.get("expense"), 0)

            if not is_valid_date_yyyy_mm_dd(day):
                flash(t.get("invalid_date"), "error")
                return redirect(url_for("edit_record", record_id=record_id, lang=lang))

            if sales < 0 or expense < 0:
                flash(t.get("invalid_amount"), "error")
                return redirect(url_for("edit_record", record_id=record_id, lang=lang))

            if sales > 1e9 or expense > 1e9:
                flash(t.get("too_large"), "error")
                return redirect(url_for("edit_record", record_id=record_id, lang=lang))

            profit = sales - expense

            conn.execute(
                "UPDATE records SET day = ?, sales = ?, expense = ?, profit = ? WHERE id = ?",
                (day, sales, expense, profit, record_id),
            )
            conn.commit()

            return redirect(url_for("index", lang=lang))

        return render_template(
            "edit_record.html",
            lang=lang,
            t=t,
            currency=currency,
            record=rec,
        )
    finally:
        conn.close()

def _parse_date(s: str):
    s = (s or "").strip()
    return s if s else None

def _export_where_clause(show_all: bool, user_id: int, start: str | None, end: str | None):
    where = []
    params = []

    if not show_all:
        where.append("r.user_id = ?")
        params.append(int(user_id))

    if start:
        where.append("r.day >= ?")
        params.append(start)
    if end:
        where.append("r.day <= ?")
        params.append(end)

    sql_where = ("WHERE " + " AND ".join(where)) if where else ""
    return sql_where, params


@app.get("/export")
@login_required
def export():
    fmt = request.args.get("fmt", "csv")
    lang = pick_lang(request)

    # Free plan kapalıysa
    if getattr(current_user, "plan", "free") == "free":
        return redirect(url_for("index", lang=lang))

    start = _parse_date(request.args.get("start"))
    end = _parse_date(request.args.get("end"))
    show_all = (request.args.get("all") == "1") and getattr(current_user, "is_admin", False)

    where_sql, params = _export_where_clause(show_all, int(current_user.id), start, end)

    conn = get_db()
    try:
        rows = conn.execute(f"""
            SELECT r.id, r.day, r.sales, r.expense, r.profit, u.username
            FROM records r
            JOIN users u ON u.id = r.user_id
            {where_sql}
            ORDER BY r.day DESC, r.id DESC
        """, params).fetchall()
    finally:
        conn.close()

    # ---------- CSV ----------
    if fmt == "csv":
        from io import StringIO
        import csv
        from flask import Response

        out = StringIO()
        w = csv.writer(out)

        if show_all:
            w.writerow(["id","day","username","sales","expense","profit"])
        else:
            w.writerow(["id","day","sales","expense","profit"])

        for r in rows:
            if show_all:
                w.writerow([r["id"], r["day"], r["username"], r["sales"], r["expense"], r["profit"]])
            else:
                w.writerow([r["id"], r["day"], r["sales"], r["expense"], r["profit"]])

        return Response(
            out.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=karapp_export.csv"}
        )

    # ---------- XLSX ----------
    elif fmt == "xlsx":
        from io import BytesIO
        from flask import send_file
        import openpyxl

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Export"

        if show_all:
            ws.append(["id","day","username","sales","expense","profit"])
        else:
            ws.append(["id","day","sales","expense","profit"])

        for r in rows:
            if show_all:
                ws.append([r["id"], r["day"], r["username"], r["sales"], r["expense"], r["profit"]])
            else:
                ws.append([r["id"], r["day"], r["sales"], r["expense"], r["profit"]])

        bio = BytesIO()
        wb.save(bio)
        bio.seek(0)

        return send_file(
            bio,
            as_attachment=True,
            download_name="karapp_export.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    # fallback
    return redirect(url_for("index", lang=lang))

@app.get("/billing")
@login_required
def billing():
    lang = pick_lang(request)
    t = I18N.get(lang, I18N["tr"])
    return render_template("billing.html", lang=lang, t=t)

import os
import stripe
from flask import abort, redirect, request, url_for
from flask_login import login_required, current_user

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")

PRICE_MONTHLY = os.environ.get("STRIPE_PRICE_ID_PRO_MONTHLY")
PRICE_YEARLY  = os.environ.get("STRIPE_PRICE_ID_PRO_YEARLY")
APP_BASE_URL  = os.environ.get("APP_BASE_URL", "http://127.0.0.1:5000")

@app.post("/billing/checkout")
@login_required
def billing_checkout():
    lang = pick_lang(request)

    cycle = (request.form.get("cycle") or "monthly").strip().lower()
    if cycle not in ("monthly", "yearly"):
        cycle = "monthly"

    price_id = PRICE_MONTHLY if cycle == "monthly" else PRICE_YEARLY
    if not price_id:
        abort(500, "Missing Stripe price id env")

    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{APP_BASE_URL}/billing/success?lang={lang}",
        cancel_url=f"{APP_BASE_URL}/billing/cancel?lang={lang}",
        client_reference_id=str(current_user.id),
        metadata={"user_id": str(current_user.id), "cycle": cycle},
    )

    return redirect(session.url, code=303)

@app.get("/billing-success")
@login_required
def billing_success():
    lang = pick_lang(request)
    t = I18N.get(lang, I18N["tr"])
    flash(t.get("billing_success", "Ödeme alındı ✅ Planın birazdan Pro olarak güncellenecek."), "success")
    return redirect(url_for("index", lang=lang))


@app.get("/billing-cancel")
@login_required
def billing_cancel():
    lang = pick_lang(request)
    t = I18N.get(lang, I18N["tr"])
    flash(t.get("billing_cancel", "Ödeme iptal edildi."), "error")
    return redirect(url_for("index", lang=lang))

import os
import stripe
from flask import request

WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")

@app.post("/stripe/webhook")
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get("Stripe-Signature")
    endpoint_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, WEBHOOK_SECRET)
    except Exception:
        return ("Bad signature", 400)

    etype = event["type"]
    obj = event["data"]["object"]

    # 1) Checkout tamamlandı => pro aç
    if etype == "checkout.session.completed":
        session = obj

        user_id = None
        if session.get("client_reference_id"):
            user_id = int(session["client_reference_id"])
        elif session.get("metadata", {}).get("user_id"):
            user_id = int(session["metadata"]["user_id"])

        if user_id:
            customer_id = session.get("customer")
            subscription_id = session.get("subscription")

            conn = get_db()
            try:
                conn.execute("""
                    UPDATE users
                    SET plan=?,
                        subscription_status=?,
                        stripe_customer_id=?,
                        stripe_subscription_id=?
                    WHERE id=?
                """, ("pro", "active", customer_id, subscription_id, user_id))
                conn.commit()
            finally:
                conn.close()

    # 2) Subscription güncellendi (iptal, ödeme düşmesi, yeniden aktif vs.)
    elif etype == "customer.subscription.updated":
        sub = obj
        status = sub.get("status")  # active, canceled, past_due, unpaid...
        sub_id = sub.get("id")

        # status'a göre plan
        new_plan = "pro" if status in ("active", "trialing") else "free"

        conn = get_db()
        try:
            conn.execute("""
                UPDATE users
                SET plan=?,
                    subscription_status=?
                WHERE stripe_subscription_id=?
            """, (new_plan, status, sub_id))
            conn.commit()
        finally:
            conn.close()

    # 3) Subscription silindi (tam iptal) => free
    elif etype == "customer.subscription.deleted":
        sub = obj
        sub_id = sub.get("id")

        conn = get_db()
        try:
            conn.execute("""
                UPDATE users
                SET plan=?,
                    subscription_status=?
                WHERE stripe_subscription_id=?
            """, ("free", "canceled", sub_id))
            conn.commit()
        finally:
            conn.close()

    return ("OK", 200)

@app.post("/create-checkout-session")
@login_required
def create_checkout_session():
    price_type = (request.form.get("type") or "monthly").strip().lower()  # monthly / yearly

    if price_type == "monthly":
        price_id = os.environ.get("STRIPE_PRICE_ID_PRO_MONTHLY")
    elif price_type == "yearly":
        price_id = os.environ.get("STRIPE_PRICE_ID_PRO_YEARLY")
    else:
        abort(400)

    if not price_id:
        # ENV'de price id yoksa erken hata
        abort(500)

    base_url = os.environ.get("APP_BASE_URL", "").rstrip("/")
    if not base_url:
        abort(500)

    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],

        # ✅ webhook’un user’ı bulması için:
        client_reference_id=str(current_user.id),
        metadata={"user_id": str(current_user.id)},

        # ✅ success/cancel (lang taşıyalım)
        success_url=os.environ.get("APP_BASE_URL") + "/billing-success",
        cancel_url=os.environ.get("APP_BASE_URL") + "/billing-cancel",

        
    )

    return redirect(session.url, code=303)

# --- Settings: GET ---
@app.get("/settings")
@login_required
def settings():
    lang = pick_lang(request)
    t = I18N.get(lang, I18N["tr"])

    # kullanılabilecek para birimleri (istediğin ekle/çıkar)
    currencies = ["SEK", "USD", "EUR", "TRY"]

    # ranges: (value, label) ; label'ları I18N ile çeviriyorum
    ranges = [
        ("0", t.get("all","Tümü")),
        ("30", "30"),
        ("90", "90"),
        ("365", "365"),
    ]

    # Eğer DB'de kolon yoksa fallback
    curr = getattr(current_user, "currency", "SEK") or "SEK"
    dr = getattr(current_user, "default_range_days", 30)
    if dr is None:
        dr = 30

    return render_template(
        "settings.html",
        lang=lang,
        t=t,
        currencies=currencies,
        ranges=ranges,
        # template'de current_user zaten kullanılıyor; yine de geçerli değer
        current_currency=curr,
        current_range=str(dr)
    )


# --- Settings: POST (form action'ın url_for('settings_post') bunu bulacak) ---
@app.post("/settings")
@login_required
def settings_post():
    lang = pick_lang(request)
    t = I18N.get(lang, I18N["tr"])

    currency = (request.form.get("currency") or "").strip().upper()
    default_range_days = request.form.get("default_range_days", "").strip()

    if not currency:
        flash(t.get("need_currency","Para birimi seçiniz"), "error")
        return redirect(url_for("settings", lang=lang))

    try:
        default_range_days_int = int(default_range_days)
    except Exception:
        default_range_days_int = 30

    conn = get_db()
    try:
        conn.execute("""
            UPDATE users
            SET currency = ?, default_range_days = ?
            WHERE id = ?
        """, (currency, default_range_days_int, int(current_user.id)))
        conn.commit()
    finally:
        conn.close()

    # Oturumdaki current_user nesnesini güncelle (UI anında değişsin)
    try:
        current_user.currency = currency
        current_user.default_range_days = default_range_days_int
    except Exception:
        pass

    flash(t.get("settings_saved","Ayarlar kaydedildi"), "success")
    return redirect(url_for("settings", lang=lang))
    
@app.get("/account")
@login_required
def account():
    lang = pick_lang(request)
    t = I18N.get(lang, I18N["tr"])

    export_allowed = (getattr(current_user, "plan", "free") == "pro")

    return render_template(
        "account.html",
        lang=lang,
        t=t,
        export_allowed=export_allowed,
    )

# ---------------- Admin: users ----------------
@app.get("/admin/users")
@login_required
@admin_required
def admin_users():
    lang = pick_lang(request)
    t = I18N.get(lang, I18N["tr"])
    currency = currency_for_lang(lang)
    
    conn = get_db()
    try:
        users = conn.execute(
            "SELECT id, username, is_admin, expires_at, plan, currency, default_range_days FROM users ORDER BY id DESC"
        ).fetchall()
    finally:
        conn.close()

    return render_template("admin_users.html", lang=lang, t=t, currency=currency, users=users)

@app.post("/admin/unlock-login")
@login_required
@admin_required
def admin_unlock_login():
    lang = pick_lang(request)
    t = I18N.get(lang, I18N["tr"])

    username = (request.form.get("username") or "").strip()
    if not username:
        flash(t.get("missing_username", "Kullanıcı adı eksik"), "error")
        return redirect(url_for("admin_users", lang=lang))

    key = username.lower()

    _login_attempts.pop(key, None)
    _login_locked_until.pop(key, None)

    flash(t.get("unlock_ok", "Login kilidi kaldırıldı"), "ok")
    return redirect(url_for("admin_users", lang=lang))

@app.post("/admin/users/create")
@login_required
@admin_required
def admin_users_create():
    lang = pick_lang(request)
    t = I18N.get(lang, I18N["tr"])
    

    username = (request.form.get("username") or "").strip()
    password = (request.form.get("password") or "").strip()
    is_admin = 1 if (request.form.get("is_admin") == "on") else 0

    days = (request.form.get("expires_days") or "").strip()
    expires_at = None
    if days:
        try:
            d = int(days)
            if d > 0:
                expires_at = (datetime.utcnow() + timedelta(days=d)).isoformat()
        except Exception:
            expires_at = None

    if not username or not password:
        flash(t.get("need_username_password"), "error")
        return redirect(url_for("admin_users", lang=lang))

    conn = get_db()
    try:
        exists = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if exists:
            flash(t.get("username_exists"), "error")
            return redirect(url_for("admin_users", lang=lang))

        conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, expires_at) VALUES (?, ?, ?, ?)",
            (username, generate_password_hash(password), is_admin, expires_at),
        )
        conn.commit()
    finally:
        conn.close()

    flash(t.get("user_created"), "ok")
    return redirect(url_for("admin_users", lang=lang))

@app.post("/admin/users/plan")
@login_required
@admin_required
def admin_users_plan():
    lang = pick_lang(request)
    t = I18N.get(lang, I18N["tr"])

    user_id = int(request.form.get("user_id") or 0)
    plan = (request.form.get("plan") or "free").strip().lower()

    if plan not in ("free", "pro"):
        flash(t.get("invalid_plan", "Invalid plan"), "error")
        return redirect(url_for("admin_users", lang=lang))

    # kendini FREE yapmayı istersen engelleyebilirsin (opsiyonel)
    # if user_id == current_user.id and plan == "free":
    #     flash("You cannot downgrade yourself.", "error")
    #     return redirect(url_for("admin_users", lang=lang))

    try:
        uid = int(user_id)
    except Exception:
        flash(t.get("invalid_user", "Invalid user"), "error")
        return redirect(url_for("admin_users", lang=lang))


    conn = get_db()
    try:
        conn.execute("UPDATE users SET plan = ? WHERE id = ?", (plan, user_id))
        conn.commit()
    finally:
        conn.close()

    flash(t.get("plan_updated", "Plan updated"), "ok")
    return redirect(url_for("admin_users", lang=lang))

@app.post("/admin/users/<int:user_id>/delete")
@login_required
@admin_required
def admin_users_delete(user_id):
    lang = pick_lang(request)
    t = I18N.get(lang, I18N["tr"])

    if int(user_id) == int(current_user.id):
        flash(t.get("cannot_delete_self"), "error")
        return redirect(url_for("admin_users", lang=lang))

    conn = get_db()
    try:
        conn.execute("DELETE FROM records WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()

    flash(t.get("user_deleted"), "ok")
    return redirect(url_for("admin_users", lang=lang))

@app.get("/api/tokens")
@login_required
def api_tokens_list():
    lang = pick_lang(request)
    t = I18N.get(lang, I18N["tr"])

    conn = get_db()
    try:
        tokens = conn.execute(
            "SELECT id, name, scopes, is_active, created_at FROM api_tokens WHERE user_id = ? ORDER BY id DESC",
            (int(current_user.id),)
        ).fetchall()
    finally:
        conn.close()

    return render_template("api_tokens.html", lang=lang, t=t, tokens=tokens)

@app.post("/api/tokens/create")
@login_required
def api_tokens_create():
    lang = pick_lang(request)
    name = (request.form.get("name") or "").strip()
    scopes = (request.form.get("scopes") or "").strip()

    # name zorunluysa kontrol et (isteğe bağlı, istersen bunu kaldırabilirsin)
    if not name:
        flash("Name required", "error")
        return redirect(url_for("api_tokens_list", lang=lang))

    # 1) raw token üret (kullanıcıya gösterilecek)
    raw_token = generate_token(32)

    # 2) veritabanına kaydetmek için hashle
    hashed = hash_token(raw_token)

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO api_tokens (user_id, token, name, scopes, is_active) VALUES (?, ?, ?, ?, 1)",
            (int(current_user.id), hashed, name, scopes)
        )
        conn.commit()
    finally:
        conn.close()

    # Kullanıcıya raw token'ı bir kere göster (template içinde uyar)
    flash("API token created. Copy it now — it will not be shown again.", "success")
    return render_template("api_token_created.html", lang=lang, token=raw_token)

@app.post("/api/tokens/revoke/<int:token_id>")
@login_required
def api_tokens_revoke(token_id):
    lang = pick_lang(request)
    token_id = request.form.get("token_id")
    if not token_id:
        abort(400)
    conn = get_db()
    try:
        conn.execute(
            "UPDATE api_tokens SET is_active = 0 WHERE id = ? AND user_id = ?",
            (token_id, int(current_user.id))
        )
        conn.commit()
    finally:
        conn.close()
    return redirect(url_for("api_tokens_list", lang=lang))


@app.get("/api/records")
@require_api_token(scopes_required=["records:read"])
def api_records_list():
    
    # request.api_user_id dekoratör tarafından atanıyorsa al, yoksa g.api_user_id kullan
    user_id = getattr(request, "api_user_id", None) or getattr(g, "api_user_id", None)
    if not user_id:
        return jsonify({"error": "no api user"}), 401

    # parse optional filters
    start = (request.args.get("start") or "").strip()
    end = (request.args.get("end") or "").strip()

    def _valid_date(s):
        try:
            datetime.strptime(s, "%Y-%m-%d")
            return True
        except:
            return False

    if (start and not _valid_date(start)) or (end and not _valid_date(end)):
        return jsonify({"error":"invalid date format (YYYY-MM-DD)"}), 400

    # try to coerce user_id to int
    try:
        user_id = int(user_id)
    except Exception:
        return jsonify({"error":"invalid api user id"}), 400

    conn = get_db()
    try:
        if start and end:
            rows = conn.execute(
                "SELECT id, day, sales, expense, profit FROM records WHERE user_id = ? AND day BETWEEN ? AND ? ORDER BY day DESC LIMIT 100",
                (user_id, start, end)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, day, sales, expense, profit FROM records WHERE user_id = ? ORDER BY day DESC LIMIT 100",
                (user_id,)
            ).fetchall()

        data = [{
            "id": r["id"],
            "day": r["day"],
            "sales": float(r["sales"] or 0),
            "expense": float(r["expense"] or 0),
            "profit": float(r["profit"] or 0),
        } for r in rows]

        return jsonify({
            "rows": data,
            "meta": {"count": len(data), "limit": 100, "start": start or None, "end": end or None}
        })
    finally:
        conn.close()
        return api_records_list()

# ---------------- Run ----------------
with app.app_context():
    init_db()

if __name__ == "__main__":
    init_db()
    ensure_admin_from_env_once()
    app.run(
        host="0.0.0.0",
        port=get_port(),
        debug=False,
        use_reloader=False
    )