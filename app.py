import os
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

from flask import (
    Flask, render_template, request,
    redirect, url_for, flash
)
from flask_login import (
    LoginManager, UserMixin,
    login_user, login_required,
    logout_user
)
from werkzeug.security import generate_password_hash, check_password_hash

# ---------------- APP ----------------
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret")

DB_PATH = Path(__file__).with_name("data.db")

# ---------------- LOGIN ----------------
login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)

class User(UserMixin):
    def __init__(self, id, username, password_hash):
        self.id = str(id)
        self.username = username
        self.password_hash = password_hash

@login_manager.user_loader
def load_user(user_id):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    return User(row["id"], row["username"], row["password_hash"])

# ---------------- DB ----------------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()

    # records
    conn.execute("""
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day TEXT NOT NULL,
            sales REAL NOT NULL,
            expense REAL NOT NULL,
            profit REAL NOT NULL
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

    # first admin
    count = conn.execute(
        "SELECT COUNT(*) FROM users"
    ).fetchone()[0]

    if count == 0:
        conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            ("admin", generate_password_hash("admin123"))
        )

    conn.commit()
    conn.close()

# ---------------- LANG ----------------
def pick_lang():
    return request.args.get("lang", "tr")

I18N = {
    "tr": {
        "title": "KaraApp",
        "subtitle": "Günlük satış, gider ve kâr takibi",
        "total_sales": "Toplam Satış",
        "total_expense": "Toplam Gider",
        "total_profit": "Toplam Kâr",
        "new_record": "Yeni Kayıt",
        "date": "Tarih",
        "sales": "Satış",
        "expense": "Gider",
        "save": "Kaydet",
        "filter": "Filtre",
        "start": "Başlangıç",
        "end": "Bitiş",
        "apply_filter": "Uygula",
        "reset": "Sıfırla",
        "daily_chart": "Günlük Grafik",
        "monthly_summary": "Aylık Özet",
        "records": "Kayıtlar",
        "delete": "Sil",
        "lang_tr": "Türkçe",
        "lang_en": "English",
        "lang_sv": "Svenska",
    }
}

CURRENCY = {"tr": "₺", "en": "$", "sv": "kr"}

# ---------------- LOGIN ROUTES ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    init_db()
    lang = pick_lang()
    t = I18N["tr"]

    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        conn = get_db()
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        ).fetchone()
        conn.close()

        if row and check_password_hash(row["password_hash"], password):
            login_user(User(row["id"], row["username"], row["password_hash"]))
            return redirect(url_for("index", saved=1))
        else:
            flash("Hatalı kullanıcı adı veya şifre")

    return render_template("login.html", lang=lang, t=t)

@app.get("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

# ---------------- MAIN ----------------
@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    init_db()
    lang = pick_lang()
    t = I18N["tr"]
    currency = CURRENCY["tr"]

    if request.method == "POST":
        day = request.form["day"]
        sales = float(request.form["sales"])
        expense = float(request.form["expense"])
        profit = sales - expense

        conn = get_db()
        conn.execute(
            "INSERT INTO records (day, sales, expense, profit) VALUES (?, ?, ?, ?)",
            (day, sales, expense, profit),
        )
        conn.commit()
        conn.close()
        return redirect(url_for("index", saved=1))

    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM records ORDER BY day DESC"
    ).fetchall()
    conn.close()

    records = [dict(r) for r in rows]

    total_sales = sum(r["sales"] for r in records)
    total_expense = sum(r["expense"] for r in records)
    total_profit = sum(r["profit"] for r in records)

    return render_template(
        "index.html",
        t=t,
        currency=currency,
        records=records,
        total_sales=round(total_sales, 2),
        total_expense=round(total_expense, 2),
        total_profit=round(total_profit, 2),
    )

@app.post("/delete/<int:record_id>")
@login_required
def delete(record_id):
    conn = get_db()
    conn.execute("DELETE FROM records WHERE id = ?", (record_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)