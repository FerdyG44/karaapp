from flask import Flask, render_template, request, redirect, url_for
import sqlite3
from pathlib import Path

app = Flask(__name__)

DB_PATH = Path(__file__).with_name("data.db")

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
    # Eski DB varsa profit kolonu ekle
    cols = [row[1] for row in conn.execute("PRAGMA table_info(records)").fetchall()]
    if "profit" not in cols:
        conn.execute("ALTER TABLE records ADD COLUMN profit REAL")
        conn.execute("UPDATE records SET profit = sales - expense WHERE profit IS NULL")

    conn.commit()
    conn.close()

# Uygulama başlarken 1 kere DB'yi hazırla
init_db()

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        day = request.form.get("day") or ""
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

        return redirect(url_for("index"))

    conn = get_db()
    rows = conn.execute("SELECT * FROM records ORDER BY day DESC, id DESC").fetchall()
    conn.close()

    total_sales = sum(r["sales"] for r in rows)
    total_expense = sum(r["expense"] for r in rows)
    total_profit = sum((r["profit"] or 0) for r in rows)

    return render_template(
        "index.html",
        records=rows,
        total_sales=round(total_sales, 2),
        total_expense=round(total_expense, 2),
        total_profit=round(total_profit, 2),
    )

@app.post("/delete/<int:record_id>")
def delete(record_id):
    conn = get_db()
    conn.execute("DELETE FROM records WHERE id = ?", (record_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)
