from flask import Flask, render_template, request, redirect, url_for
import sqlite3
from datetime import date

app = Flask(__name__)
DB = "data.db"

def init_db():
    with sqlite3.connect(DB) as con:
        cur = con.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                day TEXT NOT NULL,
                sales REAL NOT NULL,
                expense REAL NOT NULL
            )
        """)
        con.commit()

@app.route("/", methods=["GET", "POST"])
def index():
    init_db()

    if request.method == "POST":
        day = request.form.get("day") or str(date.today())
        sales = float(request.form.get("sales") or 0)
        expense = float(request.form.get("expense") or 0)

        with sqlite3.connect(DB) as con:
            cur = con.cursor()
            cur.execute(
                "INSERT INTO records(day, sales, expense) VALUES (?, ?, ?)",
                (day, sales, expense)
            )
            con.commit()

        return redirect(url_for("index"))

    with sqlite3.connect(DB) as con:
        cur = con.cursor()
        cur.execute("SELECT id, day, sales, expense FROM records ORDER BY id DESC")
        rows = cur.fetchall()

    records = []
    total_sales = 0
    total_expense = 0

    for r in rows:
        profit = r[2] - r[3]
        total_sales += r[2]
        total_expense += r[3]
        records.append({
            "id": r[0],
            "day": r[1],
            "sales": r[2],
            "expense": r[3],
            "profit": profit
        })

    total_profit = total_sales - total_expense

    return render_template(
        "index.html",
        records=records,
        total_sales=total_sales,
        total_expense=total_expense,
        total_profit=total_profit
    )

@app.route("/delete/<int:rid>", methods=["POST"])
def delete(rid):
    with sqlite3.connect(DB) as con:
        cur = con.cursor()
        cur.execute("DELETE FROM records WHERE id = ?", (rid,))
        con.commit()
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)