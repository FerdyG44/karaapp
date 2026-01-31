from flask import Flask, render_template, request, redirect, url_for
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
        "note_profit": "Not: Kâr otomatik = satış - gider",
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
        "no_monthly": "Henüz aylık özet yok.",
        "records": "Kayıtlar",
        "no_records": "Henüz kayıt yok.",
        "sales": "Satış",
        "expense": "Gider",
        "profit": "Kâr",
        "delete": "Sil",
        "language": "Dil",
    },
    "sv": {
        "title": "KaraApp",
        "subtitle": "Ange dagens försäljning och kostnader och se vinsten direkt.",
        "new_record": "Ny registrering",
        "date": "Datum",
        "daily_sales": "Försäljning",
        "daily_expense": "Kostnad",
        "save": "Spara",
        "note_profit": "Obs: Vinst = försäljning − kostnad",
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
        "no_monthly": "Ingen månadsöversikt ännu.",
        "records": "Poster",
        "no_records": "Inga poster ännu.",
        "sales": "Försäljning",
        "expense": "Kostnad",
        "profit": "Vinst",
        "delete": "Ta bort",
        "language": "Språk",
    },
    "en": {
        "title": "KaraApp",
        "subtitle": "Enter daily sales and expenses and see profit instantly.",
        "new_record": "New Record",
        "date": "Date",
        "daily_sales": "Daily sales",
        "daily_expense": "Daily expense",
        "save": "Save",
        "note_profit": "Note: Profit = sales − expense",
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
        "no_monthly": "No monthly summary yet.",
        "records": "Records",
        "no_records": "No records yet.",
        "sales": "Sales",
        "expense": "Expense",
        "profit": "Profit",
        "delete": "Delete",
        "language": "Language",
    },
}


def detect_lang():
    """
    Dil seçimi sırası:
    1) ?lang=tr|sv|en
    2) Browser Accept-Language
    3) tr
    """
    q = (request.args.get("lang") or "").lower().strip()
    if q in SUPPORTED_LANGS:
        return q

    header = (request.headers.get("Accept-Language") or "").lower()
    for code in SUPPORTED_LANGS:
        if header.startswith(code) or f"{code}-" in header or f"{code};" in header or f", {code}" in header:
            return code

    return "tr"


def t_dict(lang):
    return I18N.get(lang, I18N["tr"])


def money(x):
    try:
        return f"{float(x):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "0,00"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day TEXT NOT NULL,
            sales REAL NOT NULL,
            expense REAL NOT NULL,
            profit REAL
        )
        """
    )

    # migration: eski DB'de profit yoksa ekle
    cols = [row[1] for row in conn.execute("PRAGMA table_info(records)").fetchall()]
    if "profit" not in cols:
        conn.execute("ALTER TABLE records ADD COLUMN profit REAL")
        conn.execute("UPDATE records SET profit = sales - expense WHERE profit IS NULL")

    conn.commit()
    conn.close()


@app.route("/", methods=["GET", "POST"])
def index():
    init_db()

    lang = detect_lang()
    t = t_dict(lang)

    if request.method == "POST":
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

        # Dil parametresi kaybolmasın
        return redirect(url_for("index", lang=lang))

    # Filtre (GET)
    start = (request.args.get("start") or "").strip()
    end = (request.args.get("end") or "").strip()

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
        rows = conn.execute("SELECT * FROM records ORDER BY day DESC, id DESC").fetchall()
    conn.close()

    total_sales = sum(float(r["sales"] or 0) for r in rows)
    total_expense = sum(float(r["expense"] or 0) for r in rows)
    total_profit = sum(float(r["profit"] or 0) for r in rows)

    # Aylık özet (görünen/filtrelenmiş rows üzerinden)
    monthly = {}
    for r in rows:
        month = (r["day"] or "")[:7]  # "YYYY-MM"
        if not month:
            continue
        if month not in monthly:
            monthly[month] = {"sales": 0.0, "expense": 0.0, "profit": 0.0}
        monthly[month]["sales"] += float(r["sales"] or 0)
        monthly[month]["expense"] += float(r["expense"] or 0)
        monthly[month]["profit"] += float(r["profit"] or 0)

    monthly_rows = [{"month": m, **vals} for m, vals in sorted(monthly.items(), reverse=True)]

    return render_template(
        "index.html",
        t=t,
        lang=lang,
        supported_langs=SUPPORTED_LANGS,
        money=money,
        records=rows,
        monthly_rows=monthly_rows,
        total_sales=total_sales,
        total_expense=total_expense,
        total_profit=total_profit,
        start=start,
        end=end,
    )


@app.post("/delete/<int:record_id>")
def delete(record_id):
    init_db()
    lang = (request.args.get("lang") or "tr").lower().strip()
    if lang not in SUPPORTED_LANGS:
        lang = "tr"

    conn = get_db()
    conn.execute("DELETE FROM records WHERE id = ?", (record_id,))
    conn.commit()
    conn.close()

    return redirect(url_for("index", lang=lang))


if __name__ == "__main__":
    app.run(debug=True)