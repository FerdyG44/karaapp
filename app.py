from flask import Flask, render_template, request, redirect, url_for, make_response
import sqlite3
from pathlib import Path

app = Flask(__name__)

DB_PATH = Path(__file__).with_name("data.db")

SUPPORTED_LANGS = ["tr", "sv", "en"]

I18N = {
    "tr": {
        "title": "KaraApp",
        "subtitle": "Günlük satış ve gider gir, kârını anında gör.",
        "new_record": "Yeni Kayıt",
        "date": "Tarih",
        "daily_sales": "Günlük satış",
        "daily_expense": "Günlük gider",
        "save": "Kaydet",
        "profit_note": "Not: Kâr otomatik = satış - gider",
        "summary": "Özet",
        "total_sales": "Toplam satış",
        "total_expense": "Toplam gider",
        "total_profit": "Toplam kâr",
        "filter": "Filtre",
        "date_range": "Tarih aralığı",
        "start": "Başlangıç",
        "end": "Bitiş",
        "apply_filter": "Filtrele",
        "reset": "Sıfırla",
        "monthly_summary": "Aylık Özet",
        "month": "Ay",
        "records": "Kayıtlar",
        "no_records": "Henüz kayıt yok.",
        "sales": "Satış",
        "expense": "Gider",
        "profit": "Kâr",
        "delete": "Sil",
        "no_monthly": "Henüz aylık özet yok.",
        "language": "Dil",
        "placeholder_sales": "Örn: 30000",
        "placeholder_expense": "Örn: 11000",
    },
    "sv": {
        "title": "KaraApp",
        "subtitle": "Ange dagens försäljning och kostnader och se vinsten direkt.",
        "new_record": "Ny registrering",
        "date": "Datum",
        "daily_sales": "Dagens försäljning",
        "daily_expense": "Dagens kostnad",
        "save": "Spara",
        "profit_note": "Obs: Vinst = försäljning − kostnad",
        "summary": "Sammanfattning",
        "total_sales": "Total försäljning",
        "total_expense": "Total kostnad",
        "total_profit": "Total vinst",
        "filter": "Filter",
        "date_range": "Datumintervall",
        "start": "Start",
        "end": "Slut",
        "apply_filter": "Filtrera",
        "reset": "Återställ",
        "monthly_summary": "Månadsöversikt",
        "month": "Månad",
        "records": "Poster",
        "no_records": "Inga poster ännu.",
        "sales": "Försäljning",
        "expense": "Kostnad",
        "profit": "Vinst",
        "delete": "Ta bort",
        "no_monthly": "Ingen månadsöversikt ännu.",
        "language": "Språk",
        "placeholder_sales": "T.ex. 30000",
        "placeholder_expense": "T.ex. 11000",
    },
    "en": {
        "title": "KaraApp",
        "subtitle": "Enter daily sales and expenses and see profit instantly.",
        "new_record": "New Record",
        "date": "Date",
        "daily_sales": "Daily sales",
        "daily_expense": "Daily expense",
        "save": "Save",
        "profit_note": "Note: Profit = sales − expense",
        "summary": "Summary",
        "total_sales": "Total sales",
        "total_expense": "Total expense",
        "total_profit": "Total profit",
        "filter": "Filter",
        "date_range": "Date range",
        "start": "Start",
        "end": "End",
        "apply_filter": "Filter",
        "reset": "Reset",
        "monthly_summary": "Monthly Summary",
        "month": "Month",
        "records": "Records",
        "no_records": "No records yet.",
        "sales": "Sales",
        "expense": "Expense",
        "profit": "Profit",
        "delete": "Delete",
        "no_monthly": "No monthly summary yet.",
        "language": "Language",
        "placeholder_sales": "e.g. 30000",
        "placeholder_expense": "e.g. 11000",
    },
}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day TEXT NOT NULL,
            sales REAL NOT NULL,
            expense REAL NOT NULL,
            profit REAL
        )
    """)

    # Migration: profit kolonu yoksa ekle
    cols = [row[1] for row in conn.execute("PRAGMA table_info(records)").fetchall()]
    if "profit" not in cols:
        conn.execute("ALTER TABLE records ADD COLUMN profit REAL")
        conn.execute("UPDATE records SET profit = sales - expense WHERE profit IS NULL")

    conn.commit()
    conn.close()


def detect_lang():
    # 1) URL parametresi
    q = (request.args.get("lang") or "").strip().lower()
    if q in SUPPORTED_LANGS:
        return q

    # 2) Cookie
    c = (request.cookies.get("lang") or "").strip().lower()
    if c in SUPPORTED_LANGS:
        return c

    # 3) Accept-Language
    header = (request.headers.get("Accept-Language") or "").lower()
    if header.startswith("sv") or "sv-" in header:
        return "sv"
    if header.startswith("tr") or "tr-" in header:
        return "tr"
    if header.startswith("en") or "en-" in header:
        return "en"

    return "tr"


@app.route("/", methods=["GET", "POST"])
def index():
    init_db()

    lang = detect_lang()
    t = I18N[lang]

    # Filtre parametreleri (GET)
    start = (request.args.get("start") or "").strip()
    end = (request.args.get("end") or "").strip()

    if request.method == "POST":
        # Kayıt ekleme (POST) — mevcut filtre ve dili query ile koruyalım
        day = (request.form.get("day") or "").strip()
        sales = float(request.form.get("sales") or 0)
        expense = float(request.form.get("expense") or 0)
        profit = sales - expense

        conn = get_db()
        conn.execute(
            "INSERT INTO records (day, sales, expense, profit) VALUES (?, ?, ?, ?)",
            (day, sales, expense, profit),
        )
        conn.commit()
        conn.close()

        return redirect(url_for("index", lang=lang, start=start, end=end))

    # Kayıtları çek (filtre varsa uygula)
    conn = get_db()
    if start and end:
        rows = conn.execute(
            "SELECT * FROM records WHERE day BETWEEN ? AND ? ORDER BY day DESC, id DESC",
            (start, end),
        ).fetchall()
    elif start:
        rows = conn.execute(
            "SELECT * FROM records WHERE day >= ? ORDER BY day DESC, id DESC",
            (start,),
        ).fetchall()
    elif end:
        rows = conn.execute(
            "SELECT * FROM records WHERE day <= ? ORDER BY day DESC, id DESC",
            (end,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM records ORDER BY day DESC, id DESC"
        ).fetchall()
    conn.close()

    # Toplamlar
    total_sales = sum((r["sales"] or 0) for r in rows)
    total_expense = sum((r["expense"] or 0) for r in rows)
    total_profit = sum((r["profit"] or 0) for r in rows)

    # Aylık özet (filtrelenmiş rows üzerinden)
    monthly = {}
    for r in rows:
        month = (r["day"] or "")[:7]  # "YYYY-MM"
        if not month:
            continue
        if month not in monthly:
            monthly[month] = {"sales": 0.0, "expense": 0.0, "profit": 0.0}
        monthly[month]["sales"] += (r["sales"] or 0)
        monthly[month]["expense"] += (r["expense"] or 0)
        monthly[month]["profit"] += (r["profit"] or 0)

    monthly_rows = [
        {"month": m, **vals}
        for m, vals in sorted(monthly.items(), reverse=True)
    ]

    # Template response + cookie ile dili hatırla
    resp = make_response(
        render_template(
            "index.html",
            lang=lang,
            t=t,
            start=start,
            end=end,
            records=rows,
            monthly_rows=monthly_rows,
            total_sales=round(total_sales, 2),
            total_expense=round(total_expense, 2),
            total_profit=round(total_profit, 2),
            supported_langs=SUPPORTED_LANGS,
        )
    )
    resp.set_cookie("lang", lang, max_age=60 * 60 * 24 * 365)  # 1 yıl
    return resp


@app.post("/delete/<int:record_id>")
def delete(record_id):
    init_db()

    lang = detect_lang()
    start = (request.args.get("start") or "").strip()
    end = (request.args.get("end") or "").strip()

    conn = get_db()
    conn.execute("DELETE FROM records WHERE id = ?", (record_id,))
    conn.commit()
    conn.close()

    return redirect(url_for("index", lang=lang, start=start, end=end))


if __name__ == "__main__":
    app.run(debug=True)