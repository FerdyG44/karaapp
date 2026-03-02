"""
Initialise the ProfitApp database with sample data.

This script creates a SQLite database ``profitapp.db`` in the current
working directory with a single table ``records``.  The table stores
individual sales and expense entries.  After creating the schema, the
script populates the table with synthetic data covering the last
approximately six months (180 days).  Each day receives between
one and three sales and up to one expense.  The amounts are randomised
within realistic ranges to produce plausible aggregates.

Run this script once after cloning the repository or when resetting
the database.  Running multiple times will append additional data.
"""

import sqlite3
import datetime
import random
from pathlib import Path

DB_FILENAME = 'profitapp.db'


def initialise_database() -> None:
    """Create the database schema and insert sample data.

    This function initialises the SQLite database with a schema suitable for
    multi‑tenant use.  Each record now belongs to a specific user via the
    ``user_id`` foreign key.  A default admin user is created if none
    exist.  Sample data for the last 180 days is generated and assigned
    to the admin user.  Subsequent invocations of this script will not
    duplicate existing data.
    """
    conn = sqlite3.connect(DB_FILENAME)
    cur = conn.cursor()
    # Create users table first so that user_id foreign key can be defined.
    # Users table: include account expiration date and admin flag.  If existing
    # database lacks these columns, they will be added later.
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            plan TEXT NOT NULL DEFAULT 'Free',
            expires_at TEXT DEFAULT NULL,
            is_admin INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    # Create records table with user_id foreign key.
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            record_date TEXT NOT NULL,
            type TEXT NOT NULL CHECK (type IN ('Sale','Expense')),
            amount REAL NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    # Create sale_items table.  Each sale item belongs to a record and stores
    # item‑level details including quantity, price, discount and category.  The
    # "amount" column on records stores the net revenue after subtracting
    # discounts and VAT.  VAT rates depend on category (25% for alcohol,
    # 12% for food).
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS sale_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_id INTEGER NOT NULL,
            item_name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL,
            discount REAL NOT NULL,
            category TEXT NOT NULL CHECK (category IN ('alcohol','food')),
            FOREIGN KEY (record_id) REFERENCES records(id) ON DELETE CASCADE
        )
        """
    )
    # API tokens table.  Each token is associated with a user and has a
    # creation timestamp.  Tokens can be used for future API access.
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS api_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    conn.commit()
    # Determine existing rows to avoid duplicating sample data
    cur.execute("SELECT COUNT(*) FROM records")
    existing = cur.fetchone()[0]
    # If the users table already existed before adding expires_at/is_admin, add
    # the missing columns.  SQLite does not support dropping or altering
    # multiple columns at once, so we perform ALTER TABLE if needed.
    cur.execute("PRAGMA table_info(users)")
    existing_cols = {row[1] for row in cur.fetchall()}
    if 'expires_at' not in existing_cols:
        cur.execute("ALTER TABLE users ADD COLUMN expires_at TEXT DEFAULT NULL")
    if 'is_admin' not in existing_cols:
        # Note: new rows default to 0 (not admin)
        cur.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0")
    # Ensure at least one user exists; create admin if not.
    cur.execute("SELECT COUNT(*) FROM users")
    user_count = cur.fetchone()[0]
    if user_count == 0:
        cur.execute(
            "INSERT INTO users (username, password, plan, expires_at, is_admin) VALUES (?, ?, ?, ?, ?)",
            ('admin', 'password', 'Free', None, 1),
        )
        conn.commit()
        print("Admin user created with username 'admin', password 'password' and admin privileges.")
    if existing > 0:
        # Nothing to do if records already exist
        print(f"Database already initialised with {existing} records and {user_count} users; exiting.")
        conn.close()
        return
    # Fetch admin user's id
    cur.execute("SELECT id FROM users WHERE username = 'admin'")
    admin_id_row = cur.fetchone()
    admin_id = admin_id_row[0] if admin_id_row else 1
    # Insert synthetic data: last 180 days.  For each sale, generate a few
    # individual items with categories 'alcohol' or 'food'.  Compute the net
    # amount by subtracting discount and VAT (25% for alcohol, 12% for food).
    today = datetime.date.today()
    for days_ago in range(180, -1, -1):
        date_obj = today - datetime.timedelta(days=days_ago)
        date_str = date_obj.isoformat()
        # number of sales (1–3)
        for _ in range(random.randint(1, 3)):
            # generate between 1 and 4 items per sale
            num_items = random.randint(1, 4)
            net_total = 0.0
            # After inserting the sale record we will update its amount
            # Insert a placeholder record with zero amount to obtain the record id.
            # The query includes literal values for the type ('Sale') and amount (0),
            # so only the user_id and record_date need to be bound.
            cur.execute(
                "INSERT INTO records (user_id, record_date, type, amount) VALUES (?, ?, 'Sale', 0)",
                (admin_id, date_str),
            )
            record_id = cur.lastrowid
            for _ in range(num_items):
                category = random.choice(['alcohol', 'food'])
                quantity = random.randint(1, 5)
                price = round(random.uniform(10, 100), 2)
                # discount up to 10% of total price
                discount = round(random.uniform(0, price * quantity * 0.1), 2)
                # VAT rates: 25% for alcohol, 12% for food
                vat_rate = 0.25 if category == 'alcohol' else 0.12
                # Net revenue (excluding VAT) = (price*quantity - discount) / (1 + VAT)
                net_amount = (price * quantity - discount) / (1 + vat_rate)
                net_total += net_amount
                # Insert item row
                cur.execute(
                    "INSERT INTO sale_items (record_id, item_name, quantity, price, discount, category) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (record_id, f'Item', quantity, price, discount, category),
                )
            # Update the sale record with the computed net total
            cur.execute(
                "UPDATE records SET amount = ? WHERE id = ?",
                (round(net_total, 2), record_id),
            )
        # maybe one expense (30% chance)
        if random.random() < 0.3:
            exp_amount = round(random.uniform(20, 200), 2)
            cur.execute(
                "INSERT INTO records (user_id, record_date, type, amount) VALUES (?, ?, 'Expense', ?)",
                (admin_id, date_str, exp_amount),
            )
    conn.commit()
    conn.close()
    print("Database initialised with sample data (with sale items) and admin user.")


if __name__ == '__main__':
    initialise_database()