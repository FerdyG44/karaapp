import os
import sqlite3
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from flask import Flask, render_template, request, redirect, url_for, session
from flask_login import (
    LoginManager, UserMixin, login_user, login_required, logout_user, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash


# ---------------- App setup ----------------
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

# iOS / mobile session stability
app.config.update(
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=True,
)

DB_PATH = Path(__file__).with_name("data.db")

SUPPORTED_LANGS = ["tr", "sv", "en"]

I18N = {
    "tr": {
        "title": "KaraApp",
        "subtitle": "Günlük satış ve gider gir, kârını anında gör.",
        "lang_tr": "Türkçe",
        "lang_sv": "Svenska",
        "lang_en": "English",
        "logout": "Çıkış",
        "new_record": "Yeni Kayıt",
        "date": "Tarih",
        "sales": "Satış",
        "expense": "Gider",
        "profit": "Kâr",
        "save": "Kaydet",
        "note_profit": "Not: Kâr otomatik = satış - gider",
        "filter": "Filtre",
        "date_range": "Tarih aralığı",
        "start": "Başlangıç",
        "end": "Bitiş",
        "apply_filter": "Uygula",
        "reset": "Sıfırla",
        "kpi_sales": "Toplam satış",
        "kpi_expense": "Toplam gider",
        "kpi_profit": "Toplam kâr",
        "daily_chart": "30 Günlük Grafik",
        "monthly": "Aylık Özet",
        "month": "Ay",
        "no_monthly": "Henüz aylık özet yok.",
        "records": "Kayıtlar",
        "no_records": "Henüz kayıt yok.",
        "delete": "Sil",
        "login_title": "Giriş",
        "username": "Kullanıcı adı",
        "password": "Şifre",
        "login": "Giriş yap",
        "bad_login": "Kullanıcı adı veya şifre yanlış.",
        "admin_users": "Kullanıcı Yönetimi",
    },
    "sv": {
        "title": "KaraApp",
        "subtitle": "Ange dagens försäljning och kostnader och se vinsten direkt.",
        "lang_tr": "Türkçe",
        "lang_sv": "Svenska",
        "lang_en": "English",
        "logout": "Logga ut",
        "new_record": "Ny registrering",
        "date": "Datum",
        "sales": "Försäljning",
        "expense": "Kostnad",
        "profit": "Vinst",
        "save": "Spara",
        "note_profit": "Obs: Vinst = försäljning - kostnad",
        "filter": "Filter",
        "date_range": "Datumintervall",
        "start": "Start",
        "end": "Slut",
        "apply_filter": "Filtrera",
        "reset": "Återställ",
        "kpi_sales": "Total försäljning",
        "kpi_expense": "Total kostnad",
        "kpi_profit": "Total vinst",
        "daily_chart": "30-dagars graf",
        "monthly": "Månadsöversikt",
        "month": "Månad",
        "no_monthly": "Ingen månadsöversikt ännu.",
        "records": "Poster",
        "no_records": "Inga poster ännu.",
        "delete": "Ta bort",
        "login_title": "Logga in",
        "username": "Användarnamn",
        "password": "Lösenord",
        "login": "Logga in",
        "bad_login": "Fel användarnamn eller lösenord.",
        "admin_users": "Användarhantering",
    },
    "en": {
        "title": "KaraApp",
        "subtitle": "Enter daily sales and expenses and see profit instantly.",
        "lang_tr": "Türkçe",
        "lang_sv": "Svenska",
        "lang_en": "English",
        "logout": "Logout",
        "new_record": "New Record",
        "date": "Date",
        "sales": "Sales",
        "expense": "Expense",
        "profit": "Profit",
        "save": "Save",
        "note_profit": "Note: Profit = sales - expense",
        "filter": "Filter",
        "date_range": "Date range",
        "start": "Start",
        "end": "End",
        "apply_filter": "Apply",
        "reset": "Reset",
        "kpi_sales": "Total sales",
        "kpi_expense": "Total expense",
        "kpi_profit": "Total profit",
        "daily_chart": "30-day chart",
        "monthly": "Monthly Summary",
        "month": "Month",
        "no_monthly": "No monthly summary yet.",
        "records": "Records",
        "no_records": "No records yet.",
        "delete": "Delete",
        "login_title": "Login",
        "username": "Username",
        "password": "Password",
        "login": "Sign in",
        "bad_login": "Wrong username or password.",
        "admin_users": "User Management",
    },
}


def currency_for(lang: str) -> str:
    if lang == "sv":
        return "kr"
    if lang == "en":
        return "£"
    return "₺"


# ---------------- DB helpers ----------------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    try:
        # records
        conn.execute("""
            CREATE TABLE IF NOT EXISTS records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                day TEXT NOT NULL,
                sales REAL NOT NULL,
                expense REAL NOT NULL,
                profit REAL
            )
        """)

        # users
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )
        """)

        # migration: profit
        cols = [r[1] for r in conn.execute("PRAGMA table_info(records)").fetchall()]
        if "profit" not in cols:
            conn.execute("ALTER TABLE records ADD COLUMN profit REAL")
            conn.execute("UPDATE records SET profit = sales - expense WHERE profit IS NULL")

        # migration: user_id
        cols = [r[1] for r in conn.execute("PRAGMA table_info(records)").fetchall()]
        if "user_id" not in cols:
            conn.execute("ALTER TABLE records ADD COLUMN user_id INTEGER")
            admin = conn.execute("SELECT id FROM users ORDER BY id ASC LIMIT 1").fetchone()
            admin_id = admin["id"] if admin else 1
            conn.execute("UPDATE records SET user_id = ? WHERE user_id IS NULL", (admin_id,))

        # default admin if none exists
        exists = conn.execute("SELECT id FROM users LIMIT 1").fetchone()
        if not exists:
            conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                ("admin", generate_password_hash("admin123"))
            )

        conn.commit()
    finally:
        conn.close()


# ---------------- Language ----------------
def pick_lang(req) -> str:
    q = (req.args.get("lang") or "").lower().strip()
    if q in SUPPORTED_LANGS:
        return q

    s = (session.get("lang") or "").lower().strip()
    if s in SUPPORTED_LANGS:
        return s

    best = req.accept_languages.best_match(SUPPORTED_LANGS)
    return best or "tr"


@app.before_request
def _ensure_lang():
    if session.get("lang") in SUPPORTED_LANGS:
        return
    session["lang"] = pick_lang(request)


@app.context_processor
def _inject_common():
    lang = session.get("lang", "tr")
    if lang not in SUPPORTED_LANGS:
        lang = "tr"
    return {
        "lang": lang,
        "t": I18N[lang],
        "currency": currency_for(lang),
    }


@app.get("/set-lang/<lang_code>")
def set_lang(lang_code):
    if lang_code in SUPPORTED_LANGS:
        session["lang"] = lang_code
        session.modified = True

    nxt = request.args.get("next") or url_for("index")

    # remove lang from next URL (avoid locking language)
    try:
        u = urlparse(nxt)
        q = parse_qs(u.query)
        q.pop("lang", None)
        new_query = urlencode(q, doseq=True)
        nxt = urlunparse((u.scheme, u.netloc, u.path, u.params, new_query, u.fragment))
    except Exception:
        pass

    return redirect(nxt)


# ---------------- Login ----------------
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


class User(UserMixin):
    def __init__(self, user_id, username, password_hash):
        self.id = str(user_id)
        self.username = username
        self.password_hash = password_hash


@login_manager.user_loader
def load_user(user_id):
    conn = get_db()
    row = conn.execute(
        "SELECT id, username, password_hash FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    return User(row["id"], row["username"], row["password_hash"])


@app.route("/login", methods=["GET", "POST"])
def login():
    init_db()
    lang = session.get("lang", "tr")
    t = I18N.get(lang, I18N["tr"])

    error = None
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        conn = get_db()
        row = conn.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (username,)
        ).fetchone()
        conn.close()

        if row and check_password_hash(row["password_hash"], password):
            login_user(User(row["id"], row["username"], row["password_hash"]))
            next_url = request.args.get("next") or url_for("index")
            return redirect(next_url)
        else:
            error = t["bad_login"]

    return render_template("login.html", error=error)


@app.get("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


def is_admin():
    return current_user.is_authenticated and getattr(current_user, "username", "") == "admin"


# ---------------- Main routes ----------------
@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    init_db()

    start = (request.args.get("start") or "").strip()
    end = (request.args.get("end") or "").strip()
    uid = int(current_user.id)

    if request.method == "POST":
        day = (request.form.get("day") or "").strip()
        sales = float(request.form.get("sales") or 0)
        expense = float(request.form.get("expense") or 0)
        profit = sales - expense

        conn = get_db()
        conn.execute(
            "INSERT INTO records (day, sales, expense, profit, user_id) VALUES (?, ?, ?, ?, ?)",
            (day, sales, expense, profit, uid),
        )
        conn.commit()
        conn.close()

        return redirect(url_for("index", start=start, end=end))

    conn = get_db()

    if start and end:
        rows = conn.execute(
            "SELECT * FROM records WHERE user_id = ? AND day BETWEEN ? AND ? ORDER BY day DESC, id DESC",
            (uid, start, end),
        ).fetchall()
    elif start:
        rows = conn.execute(
            "SELECT * FROM records WHERE user_id = ? AND day >= ? ORDER BY day DESC, id DESC",
            (uid, start),
        ).fetchall()
    elif end:
        rows = conn.execute(
            "SELECT * FROM records WHERE user_id = ? AND day <= ? ORDER BY day DESC, id DESC",
            (uid, end),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM records WHERE user_id = ? ORDER BY day DESC, id DESC",
            (uid,),
        ).fetchall()

    last30 = conn.execute("""
        SELECT day,
               SUM(sales) AS sales,
               SUM(expense) AS expense,
               SUM(profit) AS profit
        FROM records
        WHERE user_id = ?
        GROUP BY day
        ORDER BY day DESC
        LIMIT 30
    """, (uid,)).fetchall()

    conn.close()

    records = [
        {
            "id": r["id"],
            "day": r["day"],
            "sales": float(r["sales"] or 0),
            "expense": float(r["expense"] or 0),
            "profit": float(r["profit"] or 0),
        }
        for r in rows
    ]

    daily_rows = [
        {
            "day": r["day"],
            "sales": float(r["sales"] or 0),
            "expense": float(r["expense"] or 0),
            "profit": float(r["profit"] or 0),
        }
        for r in reversed(last30)
    ]

    total_sales = sum(r["sales"] for r in records)
    total_expense = sum(r["expense"] for r in records)
    total_profit = sum(r["profit"] for r in records)

    monthly_map = {}
    for r in records:
        month = (r["day"] or "")[:7]
        if not month:
            continue
        if month not in monthly_map:
            monthly_map[month] = {"month": month, "sales": 0.0, "expense": 0.0, "profit": 0.0}
        monthly_map[month]["sales"] += r["sales"]
        monthly_map[month]["expense"] += r["expense"]
        monthly_map[month]["profit"] += r["profit"]

    monthly_rows = [monthly_map[m] for m in sorted(monthly_map.keys())]

    return render_template(
        "index.html",
        start=start,
        end=end,
        records=records,
        daily_rows=daily_rows,
        monthly_rows=monthly_rows,
        total_sales=round(total_sales, 2),
        total_expense=round(total_expense, 2),
        total_profit=round(total_profit, 2),
    )


@app.post("/delete/<int:record_id>")
@login_required
def delete(record_id):
    init_db()

    start = (request.args.get("start") or "").strip()
    end = (request.args.get("end") or "").strip()
    uid = int(current_user.id)

    conn = get_db()
    conn.execute("DELETE FROM records WHERE id = ? AND user_id = ?", (record_id, uid))
    conn.commit()
    conn.close()

    return redirect(url_for("index", start=start, end=end))


# ---------------- Admin: user management ----------------
@app.route("/admin/users", methods=["GET", "POST"])
@login_required
def admin_users():
    if not is_admin():
        return "Forbidden", 403

    init_db()

    msg = None
    err = None

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        if not username or not password:
            err = "Username and password required."
        else:
            conn = get_db()
            exists = conn.execute(
                "SELECT id FROM users WHERE username = ?",
                (username,)
            ).fetchone()

            if exists:
                err = "Username already exists."
            else:
                conn.execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    (username, generate_password_hash(password))
                )
                conn.commit()
                msg = "User created."

            conn.close()

    conn = get_db()
    users = conn.execute(
        "SELECT id, username FROM users ORDER BY id DESC"
    ).fetchall()
    conn.close()

    users_list = [{"id": u["id"], "username": u["username"]} for u in users]

    return render_template("admin_users.html", users=users_list, msg=msg, err=err)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)