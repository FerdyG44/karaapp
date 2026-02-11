import os
import re
import sqlite3
import threading
import time
import csv

import csv
from io import StringIO
from flask import Response


from io import BytesIO

from datetime import datetime, timedelta
from functools import wraps
from collections import defaultdict

from io import StringIO
from flask import Response
from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, abort, session
)
from werkzeug.security import generate_password_hash, check_password_hash

from flask_login import (
    LoginManager, UserMixin,
    login_user, logout_user,
    login_required, current_user
)

from flask_wtf.csrf import CSRFProtect

# ---------------- App ----------------
app = Flask(__name__)
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

IS_PROD = (os.environ.get("RENDER") == "true") or (os.environ.get("FLASK_ENV") == "production")

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=IS_PROD,   # prod: True / local: False
)

csrf = CSRFProtect(app)

from flask_wtf.csrf import CSRFError

@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    lang = pick_lang(request)
    t = I18N.get(lang, I18N["tr"])
    flash(t.get("csrf_error", "Güvenlik doğrulaması başarısız. Sayfayı yenileyip tekrar dene."), "error")
    return redirect(request.referrer or url_for("login", lang=lang))

# ---------------- Config ----------------

DATA_DIR = os.getenv("DATA_DIR", "data")
os.makedirs(DATA_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "data.db")

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

_login_attempts = defaultdict(list)  # key -> [timestamps]
MAX_ATTEMPTS = 8
WINDOW_SECONDS = 10 * 60   # 10 dk
LOCK_SECONDS = 15 * 60     # 15 dk
_login_locked_until = {}   # key -> unix time

# ---------------- DB helpers ----------------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_admin INTEGER NOT NULL DEFAULT 0,
                expires_at TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                day TEXT NOT NULL,
                sales REAL NOT NULL,
                expense REAL NOT NULL,
                profit REAL
            )
        """)

        # migration: add profit if missing
        cols = [r[1] for r in conn.execute("PRAGMA table_info(records)").fetchall()]
        if "profit" not in cols:
            conn.execute("ALTER TABLE records ADD COLUMN profit REAL")
            conn.execute("UPDATE records SET profit = sales - expense WHERE profit IS NULL")

        # migration: add user_id if missing
        cols = [r[1] for r in conn.execute("PRAGMA table_info(records)").fetchall()]
        if "user_id" not in cols:
            conn.execute("ALTER TABLE records ADD COLUMN user_id INTEGER")
            # attach old records to first user (admin)
            admin = conn.execute("SELECT id FROM users ORDER BY id ASC LIMIT 1").fetchone()
            admin_id = admin["id"] if admin else 1
            conn.execute("UPDATE records SET user_id = ? WHERE user_id IS NULL", (admin_id,))

        # migration: add plan if missing
        cols = [r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
        if "plan" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN plan TEXT DEFAULT 'free'")
        
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
    def __init__(self, id, username, password_hash, is_admin=0, expires_at=None, plan="free"):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.is_admin = is_admin
        self.expires_at = expires_at
        self.plan = plan or "free"
        
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
    currency = currency_for_lang(lang)

    show_all = (request.args.get("all") == "1") and getattr(current_user, "is_admin", False)

    # --- A4: Range filtresi ---
    range_days = (request.args.get("range") or "").strip()
    
    start = None
    end = None

    if range_days.isdigit():
        d = int(range_days)
        if d > 0:
            start = (datetime.now() - timedelta(days=d)).strftime("%Y-%m-%d")
            end = datetime.now().strftime("%Y-%m-%d")

    conn = get_db()
    try:
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
            start=start,
            end=end,
            range_days=range_days,
            selected_range = (request.args.get("range") or "").strip()
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

@app.get("/export.csv")
@login_required
def export_csv():
    lang = pick_lang(request)
    t = I18N.get(lang, I18N["tr"])

    if current_user.plan == "free":
        return redirect(url_for("index", lang=lang))

    # filtreler
    start = _parse_date(request.args.get("start"))
    end = _parse_date(request.args.get("end"))

    # admin all
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

    out = StringIO()
    w = csv.writer(out)

    # header
    if show_all:
        w.writerow(["id", "day", "username", "sales", "expense", "profit"])
    else:
        w.writerow(["id", "day", "sales", "expense", "profit"])

    for r in rows:
        if show_all:
            w.writerow([r["id"], r["day"], r["username"], r["sales"], r["expense"], r["profit"]])
        else:
            w.writerow([r["id"], r["day"], r["sales"], r["expense"], r["profit"]])

    # ---- filename (date + range) ----
    start_q = (request.args.get("start") or "").strip()
    end_q = (request.args.get("end") or "").strip()
    range_q = (request.args.get("range") or "").strip()

    start_part = start_q if start_q else "NA"
    end_part = end_q if end_q else "NA"
    range_part = f"range-{range_q}" if range_q else "range-all"

    scope_part = (
        "ALL"
        if (request.args.get("all") == "1" and getattr(current_user, "is_admin", False))
        else f"user-{current_user.id}"
    )

    filename = f"karapp_{scope_part}_{start_part}_{end_part}_{range_part}.csv"

    return Response(
        out.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@app.get("/export.xlsx")
@login_required
def export_xlsx():
    from openpyxl import Workbook
    lang = pick_lang(request)
    t = I18N.get(lang, I18N["tr"])

    if current_user.plan == "free":
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

    from io import BytesIO
    from flask import send_file
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Export"

    if show_all:
        ws.append(["id", "day", "username", "sales", "expense", "profit"])
    else:
        ws.append(["id", "day", "sales", "expense", "profit"])

    for r in rows:
        if show_all:
            ws.append([r["id"], r["day"], r["username"], r["sales"], r["expense"], r["profit"]])
        else:
            ws.append([r["id"], r["day"], r["sales"], r["expense"], r["profit"]])

    bio = BytesIO()
    wb.save(bio)
    bio.seek(0)

# ---- filename (date + range) ----
    start_q = (request.args.get("start") or "").strip()
    end_q = (request.args.get("end") or "").strip()
    range_q = (request.args.get("range") or "").strip()

    start_part = start_q if start_q else "NA"
    end_part = end_q if end_q else "NA"
    range_part = f"range-{range_q}" if range_q else "range-all"

    scope_part = (
        "ALL"
        if (request.args.get("all") == "1" and getattr(current_user, "is_admin", False))
        else f"user-{current_user.id}"
)

    filename: str = f"karapp_{scope_part}_{start_part}_{end_part}_{range_part}.xlsx"    

    return send_file(
        bio,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
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
            "SELECT id, username, is_admin, expires_at FROM users ORDER BY id DESC"
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


# ---------------- Run ----------------
if __name__ == "__main__":
    init_db()
    ensure_admin_from_env_once()
    app.run(
        host="0.0.0.0",
        port=get_port(),
        debug=False,
        use_reloader=False
    )