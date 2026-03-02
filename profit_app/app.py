"""
ProfitApp Flask application
This application provides a simple dashboard for tracking sales and expenses and
presents a live overview of profits.  It exposes a minimal API for
retrieving summary metrics, fetching recent records and adding new records.

The data is stored locally in a SQLite database (`profitapp.db`). Each
record consists of a date, a type (either ``Sale`` or ``Expense``) and an
amount.  Sales contribute positively to the total while expenses reduce
profit.  The application computes both per‑day and aggregate totals and
exposes them via JSON endpoints consumed by the front‑end.

To run the application locally:

.. code-block:: bash

    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    python3 init_db.py  # only the first time to create sample data
    python3 app.py

Then visit ``http://127.0.0.1:5000`` in your browser.  The dashboard
will refresh itself automatically every few seconds to reflect live
changes.
"""

import sqlite3
import datetime
from pathlib import Path
from flask import (
    Flask,
    render_template,
    jsonify,
    request,
    session,
    redirect,
    url_for,
    send_file,
    make_response,
    abort,
)

# Create the Flask application early so route decorators defined below work properly.
app = Flask(__name__)
import csv
import io
import openpyxl
import secrets

########################################
# Localization and translation support
########################################

# Translation dictionary for supported languages.  These strings will
# appear in user management, token, account and settings pages.  For
# pages translated client side via JavaScript (the dashboard), see
# static/script.js.

TRANSLATIONS = {
    'en': {
        'manage_users': 'Manage Users',
        'logged_in_as': 'Logged in as',
        'back_to_dashboard': 'Back to dashboard',
        'id': 'ID',
        'username': 'Username',
        'plan': 'Plan',
        'tokens': 'Tokens',
        'actions': 'Actions',
        'delete': 'Delete',
        'new_token': 'New Token',
        'add_user': 'Add User',
        'password': 'Password',
        'add': 'Add',
        'api_tokens_title': 'Your API Tokens',
        'no_tokens': 'You have no API tokens.',
        'generate_token': 'Generate New Token',
        'account': 'Account',
        'account_placeholder': 'This is a placeholder account page. Future versions could allow you to change your password or personal settings.',
        'change_password_title': 'Change Password',
        'new_password': 'New Password',
        'confirm_password': 'Confirm Password',
        'change': 'Change',
        'settings': 'Settings',
        'settings_placeholder': 'This is a placeholder settings page. Here you might configure language preferences or other personal settings in a future version.',
        'select_language': 'Select language',
        'save': 'Save',
        'password_change_success': 'Password updated successfully.',
        'password_change_error': 'Password update failed.',
        # Notices about plan limits
        'free_plan_notice': 'Free plan includes limited features. You can have up to 2 API tokens. Upgrade to Pro for unlimited tokens.',
        'pro_plan_notice': 'You\'re on Pro plan. Unlimited tokens.',
        # Additional UI strings
        'welcome': 'Welcome',
        'logout': 'Logout',
        'all_records': 'All records',
        'go_pro': 'Go Pro',
        'go_pro_hint': 'Upgrade plan',
        'change_username_title': 'Change Username',
        'new_username': 'New Username',
        'confirm_username': 'Confirm Username',
        'username_change_success': 'Username updated successfully.',
        'username_change_error': 'Username update failed.',
        'expires_at_label': 'Expires',
    },
    'tr': {
        'manage_users': 'Kullanıcıları Yönet',
        'logged_in_as': 'Giriş yapan',
        'back_to_dashboard': 'Ana sayfaya dön',
        'id': 'ID',
        'username': 'Kullanıcı Adı',
        'plan': 'Plan',
        'tokens': 'Tokenlar',
        'actions': 'Eylemler',
        'delete': 'Sil',
        'new_token': 'Yeni Token',
        'add_user': 'Kullanıcı Ekle',
        'password': 'Parola',
        'add': 'Ekle',
        'api_tokens_title': 'API Tokenlarınız',
        'no_tokens': 'Hiç API tokenınız yok.',
        'generate_token': 'Yeni Token Üret',
        'account': 'Hesap',
        'account_placeholder': 'Bu bir yer tutucu hesap sayfasıdır. Gelecekteki sürümler şifrenizi veya kişisel ayarlarınızı değiştirmenize izin verebilir.',
        'change_password_title': 'Parola Değiştir',
        'new_password': 'Yeni Parola',
        'confirm_password': 'Parolayı Onayla',
        'change': 'Değiştir',
        'settings': 'Ayarlar',
        'settings_placeholder': 'Bu bir yer tutucu ayarlar sayfasıdır. Gelecekte dil tercihlerini veya diğer kişisel ayarları yapılandırabilirsiniz.',
        'select_language': 'Dil seç',
        'save': 'Kaydet',
        'password_change_success': 'Parola başarıyla güncellendi.',
        'password_change_error': 'Parola güncellenemedi.',
        # Notices about plan limits
        'free_plan_notice': 'Ücretsiz plan sınırlı özellikler içerir. En fazla 2 API tokenınız olabilir. Sınırsız token için Pro\'ya yükseltin.',
        'pro_plan_notice': 'Pro plan kullanıyorsunuz. Sınırsız token hakkınız var.',
        # Additional UI strings
        'welcome': 'Hoş geldiniz',
        'logout': 'Çıkış',
        'all_records': 'Tüm kayıtlar',
        'go_pro': 'Pro ol',
        'go_pro_hint': 'Planı yükselt',
        'change_username_title': 'Kullanıcı Adını Değiştir',
        'new_username': 'Yeni Kullanıcı Adı',
        'confirm_username': 'Kullanıcı Adını Onayla',
        'username_change_success': 'Kullanıcı adı başarıyla güncellendi.',
        'username_change_error': 'Kullanıcı adı güncellenemedi.',
        'expires_at_label': 'Son Tarih',
    },
    'sv': {
        'manage_users': 'Hantera användare',
        'logged_in_as': 'Inloggad som',
        'back_to_dashboard': 'Tillbaka till instrumentpanelen',
        'id': 'ID',
        'username': 'Användarnamn',
        'plan': 'Plan',
        'tokens': 'Token',
        'actions': 'Åtgärder',
        'delete': 'Radera',
        'new_token': 'Ny Token',
        'add_user': 'Lägg till användare',
        'password': 'Lösenord',
        'add': 'Lägg till',
        'api_tokens_title': 'Dina API-token',
        'no_tokens': 'Du har inga API-token.',
        'generate_token': 'Generera ny token',
        'account': 'Konto',
        'account_placeholder': 'Detta är en platshållarsida. Framtida versioner kan låta dig ändra lösenord eller personliga inställningar.',
        'change_password_title': 'Byt lösenord',
        'new_password': 'Nytt lösenord',
        'confirm_password': 'Bekräfta lösenord',
        'change': 'Ändra',
        'settings': 'Inställningar',
        'settings_placeholder': 'Detta är en platshållarsida för inställningar. Här kan du i framtiden konfigurera språk eller andra personliga inställningar.',
        'select_language': 'Välj språk',
        'save': 'Spara',
        'password_change_success': 'Lösenordet har uppdaterats.',
        'password_change_error': 'Misslyckades med att uppdatera lösenordet.',
        # Notices about plan limits
        'free_plan_notice': 'Gratisplanen har begränsade funktioner. Du kan ha upp till 2 API-token. Uppgradera till Pro för obegränsade tokens.',
        'pro_plan_notice': 'Du har Pro-plan. Obegränsade tokens.',
        # Additional UI strings
        'welcome': 'Välkommen',
        'logout': 'Logga ut',
        'all_records': 'Alla poster',
        'go_pro': 'Go Pro',
        'go_pro_hint': 'Uppgradera plan',
        'change_username_title': 'Byt användarnamn',
        'new_username': 'Nytt användarnamn',
        'confirm_username': 'Bekräfta användarnamn',
        'username_change_success': 'Användarnamnet har uppdaterats.',
        'username_change_error': 'Misslyckades med att uppdatera användarnamnet.',
        'expires_at_label': 'Förfaller',
    },
}

def get_current_language() -> str:
    """Return the current language stored in the session or default to English."""
    return session.get('lang', 'en')

@app.route('/set_lang')
def set_language():
    """Set the current language in the session based on query parameter ``lang``."""
    lang = request.args.get('lang')
    if lang in TRANSLATIONS:
        session['lang'] = lang
    # Optionally redirect back to referring page
    next_url = request.args.get('next') or request.headers.get('Referer') or url_for('index')
    return redirect(next_url)
########################################
# Authentication helpers
########################################

def get_current_user():
    """Return the currently logged in user row or None if not authenticated.

    The returned row includes ``expires_at`` and ``is_admin`` fields so that
    downstream functions can enforce account expiration and admin privileges
    without performing additional queries.  If no user is logged in the
    session, ``None`` is returned.
    """
    user_id = session.get('user_id')
    if not user_id:
        return None
    with get_db_connection() as conn:
        cur = conn.execute(
            "SELECT id, username, plan, expires_at, is_admin FROM users WHERE id = ?",
            (user_id,),
        )
        row = cur.fetchone()
        return row


def login_required(fn):
    """Decorator to enforce authentication for routes serving HTML pages."""
    from functools import wraps

    @wraps(fn)
    def wrapper(*args, **kwargs):
        # Require login
        if not session.get('user_id'):
            return redirect(url_for('login', next=request.path))
        # Check for account expiration on each request
        current = get_current_user()
        if current:
            expires_at = current['expires_at']
            if expires_at:
                try:
                    expiry_date = datetime.date.fromisoformat(expires_at)
                    if expiry_date < datetime.date.today():
                        # Expired: log out and redirect to login
                        session.pop('user_id', None)
                        return redirect(url_for('login', next=request.path))
                except Exception:
                    pass
        return fn(*args, **kwargs)

    return wrapper


# The database file.  Stored relative to the application root so it persists
# across restarts but remains local to this project.
DB_FILENAME = 'profitapp.db'

# The Flask application was created above.  Do not redefine it here.

# Secret key used to sign session cookies.  In a real application this
# value should be set from an environment variable and kept secret.  It
# enables user authentication via the Flask session object.
app.secret_key = 'replace-this-with-a-random-secret'

def get_db_connection() -> sqlite3.Connection:
    """Return a new connection to the SQLite database.

    Connections are created on demand and closed automatically by the context
    manager in the calling functions.  The row factory is set so results
    behave like dictionaries.
    """
    conn = sqlite3.connect(DB_FILENAME)
    conn.row_factory = sqlite3.Row
    return conn


@app.route('/')
@login_required
def index() -> str:
    """Render the main dashboard page.

    The page is delivered as an HTML template.  All dynamic content is
    populated client side via JavaScript by calling JSON APIs exposed by
    this backend.  Only authenticated users can access the dashboard.
    """
    today = datetime.date.today().isoformat()
    user = get_current_user()
    # Provide translation dictionary for the current language
    lang = get_current_language()
    t = TRANSLATIONS.get(lang, TRANSLATIONS['en'])
    return render_template('index.html', today=today, user=user, t=t, lang=lang)


@app.route('/api/summary')
def api_summary() -> 'flask.Response':
    """Return aggregate and today's summary statistics as JSON.

    The summary includes totals for sales, expenses and profit across the
    entire dataset along with the same metrics restricted to the current
    calendar date.  Missing values are treated as zero.
    """
    today_str = datetime.date.today().isoformat()
    # Determine current user; if not logged in use None which yields no data
    current = get_current_user()
    user_id = current['id'] if current else None
    with get_db_connection() as conn:
        # Overall totals filtered by user
        cur = conn.execute(
            """
            SELECT
                IFNULL(SUM(CASE WHEN type='Sale' THEN amount END), 0) AS total_sales,
                IFNULL(SUM(CASE WHEN type='Expense' THEN amount END), 0) AS total_expenses,
                COUNT(CASE WHEN type='Sale' THEN 1 END) AS total_orders,
                IFNULL(SUM(CASE WHEN type='Sale' THEN (
                    SELECT SUM(si.quantity)
                    FROM sale_items si WHERE si.record_id = records.id
                ) END), 0) AS total_items,
                IFNULL(SUM(CASE WHEN type='Sale' THEN (
                    SELECT SUM(si.discount)
                    FROM sale_items si WHERE si.record_id = records.id
                ) END), 0) AS total_discount,
                IFNULL(SUM(CASE WHEN type='Sale' THEN (
                    SELECT SUM(si.price * si.quantity)
                    FROM sale_items si WHERE si.record_id = records.id
                ) END), 0) AS total_gross
            FROM records
            WHERE user_id = ?
            """,
            (user_id,),
        )
        row = cur.fetchone()
        total_sales = float(row['total_sales'] or 0)
        total_expenses = float(row['total_expenses'] or 0)
        total_profit = total_sales - total_expenses
        total_orders = int(row['total_orders'] or 0)
        total_items = int(row['total_items'] or 0)
        total_discount = float(row['total_discount'] or 0)
        total_gross = float(row['total_gross'] or 0)
        total_avg_sale = total_sales / total_orders if total_orders > 0 else 0
        # Today's totals filtered by user
        cur = conn.execute(
            """
            SELECT
                IFNULL(SUM(CASE WHEN type='Sale' THEN amount END), 0) AS day_sales,
                IFNULL(SUM(CASE WHEN type='Expense' THEN amount END), 0) AS day_expenses,
                COUNT(CASE WHEN type='Sale' THEN 1 END) AS day_orders,
                IFNULL(SUM(CASE WHEN type='Sale' THEN (
                    SELECT SUM(si.quantity)
                    FROM sale_items si WHERE si.record_id = records.id
                ) END), 0) AS day_items,
                IFNULL(SUM(CASE WHEN type='Sale' THEN (
                    SELECT SUM(si.discount)
                    FROM sale_items si WHERE si.record_id = records.id
                ) END), 0) AS day_discount,
                IFNULL(SUM(CASE WHEN type='Sale' THEN (
                    SELECT SUM(si.price * si.quantity)
                    FROM sale_items si WHERE si.record_id = records.id
                ) END), 0) AS day_gross
            FROM records
            WHERE user_id = ? AND record_date = ?
            """,
            (user_id, today_str),
        )
        row2 = cur.fetchone()
        day_sales = float(row2['day_sales'] or 0)
        day_expenses = float(row2['day_expenses'] or 0)
        day_profit = day_sales - day_expenses
        day_orders = int(row2['day_orders'] or 0)
        day_items = int(row2['day_items'] or 0)
        day_discount = float(row2['day_discount'] or 0)
        day_gross = float(row2['day_gross'] or 0)
        day_avg_sale = day_sales / day_orders if day_orders > 0 else 0
    # Format as JSON including additional metrics
    return jsonify(
        {
            'today_date': today_str,
            'today_sales': day_sales,
            'today_expenses': day_expenses,
            'today_profit': day_profit,
            'today_orders': day_orders,
            'today_items': day_items,
            'today_discount': day_discount,
            'today_gross': day_gross,
            'today_avg_sale': day_avg_sale,
            'total_sales': total_sales,
            'total_expenses': total_expenses,
            'total_profit': total_profit,
            'total_orders': total_orders,
            'total_items': total_items,
            'total_discount': total_discount,
            'total_gross': total_gross,
            'total_avg_sale': total_avg_sale,
        }
    )


@app.route('/api/records')
def api_records() -> 'flask.Response':
    """Return a list of the most recent records as JSON.

    Query parameters:
        ``limit`` – maximum number of records to return (default 50)
        ``days`` – if provided, restrict records to those in the last N days
            relative to today.

    Results are ordered with the most recent records first (by date then id).
    """
    limit = request.args.get('limit', default=50, type=int)
    days = request.args.get('days', default=None, type=int)
    query = "SELECT id, record_date, type, amount FROM records"
    params = []
    where_clauses = []
    # Always restrict to the current user
    current = get_current_user()
    user_id = current['id'] if current else None
    if user_id is not None:
        where_clauses.append("user_id = ?")
        params.append(user_id)
    if days is not None:
        # Compute date threshold: records on or after this date
        threshold = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
        where_clauses.append("record_date >= ?")
        params.append(threshold)
    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)
    query += " ORDER BY record_date DESC, id DESC LIMIT ?"
    params.append(limit)
    with get_db_connection() as conn:
        cur = conn.execute(query, params)
        rows = cur.fetchall()
    # Convert Row objects into plain dicts and format numbers consistently
    records = []
    for r in rows:
        records.append(
            {
                'id': r['id'],
                'record_date': r['record_date'],
                'type': r['type'],
                'amount': float(r['amount']),
            }
        )
    return jsonify({'records': records})


@app.route('/api/add_record', methods=['POST'])
def api_add_record() -> 'flask.Response':
    """Create a new record from JSON payload.

    The request body must be JSON and contain the keys ``record_date``,
    ``type`` and ``amount``.  ``record_date`` should be an ISO date string
    (YYYY‑MM‑DD).  ``type`` should be either ``Sale`` or ``Expense``.  The
    ``amount`` value may be a string or number and will be coerced to a
    float.  Invalid input will result in a 400 error.
    """
    try:
        data = request.get_json(force=True)
        record_date = data.get('record_date')
        rec_type = data.get('type')
        amount = float(data.get('amount'))
    except Exception:
        return jsonify({'error': 'Invalid request data'}), 400
    if not record_date or rec_type not in ('Sale', 'Expense'):
        return jsonify({'error': 'Missing or invalid fields'}), 400
    # Validate date format
    try:
        datetime.date.fromisoformat(record_date)
    except ValueError:
        return jsonify({'error': 'Invalid date format'}), 400
    # Determine current user
    current = get_current_user()
    user_id = current['id'] if current else None
    with get_db_connection() as conn:
        conn.execute(
            "INSERT INTO records (user_id, record_date, type, amount) VALUES (?, ?, ?, ?)",
            (user_id, record_date, rec_type, amount),
        )
        conn.commit()
    return jsonify({'success': True})

#
# External POS integration
#
# This endpoint allows external cash registers or POS devices to send sales
# directly to the application.  The payload must be JSON with an "amount"
# field.  Optionally, a "record_date" field may be provided.  The
# current logged in user will be used to associate the sale.  If no user
# is logged in, the sale will still be recorded with a null user_id.

@app.route('/api/pos_sale', methods=['POST'])
def api_pos_sale() -> 'flask.Response':
    """Receive a sale event from an external POS device and record it.

    The JSON payload should contain either:

    - ``amount``: the net amount of the sale (after discounts and VAT).  In this
      case no item details are recorded.
    - or ``items``: a list of item dictionaries.  Each item must include
      ``item_name``, ``quantity``, ``price`` and ``category``.  A ``discount``
      field may optionally be provided for each item.  The net sale amount
      will be computed from the item list by subtracting the discount and
      removing VAT (25% for alcohol, 12% for food).  The items will be
      stored in the ``sale_items`` table.

    Optionally ``record_date`` may be provided as an ISO date or full
    datetime string.  If omitted, today's date is used.  The sale is always
    recorded with type "Sale".  If both ``amount`` and ``items`` are
    provided, the item list takes precedence and ``amount`` is ignored.
    """
    try:
        data = request.get_json(force=True) or {}
    except Exception:
        return jsonify({'error': 'Invalid JSON'}), 400
    # Determine record_date: accept provided or use today's date
    record_date = data.get('record_date')
    if record_date:
        try:
            # Accept full datetime; keep only date part
            if 'T' in record_date:
                record_date = record_date.split('T')[0]
            datetime.date.fromisoformat(record_date)
        except Exception:
            return jsonify({'error': 'Invalid record_date'}), 400
    else:
        record_date = datetime.date.today().isoformat()
    # Determine current user id
    current = get_current_user()
    user_id = current['id'] if current else None
    items = data.get('items')
    net_total = None
    if items and isinstance(items, list) and len(items) > 0:
        # Compute net total from item details
        net_total = 0.0
        # We'll store item details after creating the record
    else:
        # Fallback to amount
        amount = data.get('amount')
        if amount is None:
            return jsonify({'error': 'Missing amount or items'}), 400
        try:
            net_total = float(amount)
        except Exception:
            return jsonify({'error': 'Invalid amount'}), 400
    with get_db_connection() as conn:
        cur = conn.cursor()
        # Create sale record with provisional amount (0) to get record id
        cur.execute(
            "INSERT INTO records (user_id, record_date, type, amount) VALUES (?, ?, 'Sale', 0)",
            (user_id, record_date),
        )
        record_id = cur.lastrowid
        # If item list exists, insert items and compute net_total
        if items and isinstance(items, list) and len(items) > 0:
            net_total = 0.0
            for item in items:
                item_name = item.get('item_name') or item.get('name') or 'Item'
                try:
                    quantity = int(item.get('quantity', 1))
                except Exception:
                    quantity = 1
                try:
                    price = float(item.get('price', 0))
                except Exception:
                    price = 0.0
                try:
                    discount = float(item.get('discount', 0))
                except Exception:
                    discount = 0.0
                category = item.get('category', 'food')
                if category not in ('alcohol', 'food'):
                    category = 'food'
                vat_rate = 0.25 if category == 'alcohol' else 0.12
                # Net revenue (excluding VAT) = (price*quantity - discount) / (1 + VAT)
                net = (price * quantity - discount) / (1 + vat_rate) if price * quantity > 0 else 0.0
                net_total += net
                cur.execute(
                    "INSERT INTO sale_items (record_id, item_name, quantity, price, discount, category)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (record_id, item_name, quantity, price, discount, category),
                )
        # Update sale record with computed net total
        cur.execute(
            "UPDATE records SET amount = ? WHERE id = ?",
            (round(net_total, 2), record_id),
        )
        conn.commit()
    return jsonify({'success': True})


# ------------------------
# Authentication endpoints
# ------------------------

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Render and process the login form.

    If the method is GET, display a simple login form.  If POST, verify
    credentials and set the session.  Supports redirecting to the page
    originally requested via the ``next`` query parameter.
    """
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not username or not password:
            return render_template('login.html', error='Please enter username and password.')
        with get_db_connection() as conn:
            cur = conn.execute(
                "SELECT id, password FROM users WHERE username = ?",
                (username,),
            )
            user = cur.fetchone()
            if not user or user['password'] != password:
                return render_template('login.html', error='Invalid credentials.')
            # Login successful
            session['user_id'] = user['id']
            # Redirect to next page or index
            next_url = request.args.get('next') or url_for('index')
            return redirect(next_url)
    # GET
    return render_template('login.html', error=None)


@app.route('/logout')
def logout():
    """Log the user out by clearing the session and redirect to login."""
    session.pop('user_id', None)
    return redirect(url_for('login'))


# ------------------------
# User management endpoints and views
# ------------------------

@app.route('/users')
@login_required
def users_page():
    """Render the manage users page for administrators only.

    Only users with the ``is_admin`` flag set may access this view.
    Non‑admin users will see a 403 error.
    """
    current = get_current_user()
    # Require admin privileges
    if not current or not current['is_admin']:
        abort(403)
    with get_db_connection() as conn:
        # Fetch all users and their plans.  Include expiration date and admin flag
        cur = conn.execute(
            "SELECT id, username, plan, expires_at, is_admin FROM users ORDER BY id ASC"
        )
        users = [
            dict(
                id=row['id'],
                username=row['username'],
                plan=row['plan'],
                expires_at=row['expires_at'],
                is_admin=bool(row['is_admin']),
            )
            for row in cur.fetchall()
        ]
        # Fetch tokens for each user
        tokens: dict[int, list[str]] = {}
        cur = conn.execute(
            "SELECT user_id, token FROM api_tokens ORDER BY created_at DESC"
        )
        for row in cur.fetchall():
            tokens.setdefault(row['user_id'], []).append(row['token'])
    # Provide translations
    lang = get_current_language()
    t = TRANSLATIONS.get(lang, TRANSLATIONS['en'])
    return render_template('users.html', users=users, tokens=tokens, user=current, t=t)


@app.route('/api/users')
@login_required
def api_users():
    """Return a list of all users.  Admin only."""
    current = get_current_user()
    if not current or not current['is_admin']:
        return jsonify({'error': 'Forbidden'}), 403
    with get_db_connection() as conn:
        cur = conn.execute(
            "SELECT id, username, plan, expires_at, is_admin FROM users ORDER BY id ASC"
        )
        users = [
            dict(
                id=row['id'],
                username=row['username'],
                plan=row['plan'],
                expires_at=row['expires_at'],
                is_admin=bool(row['is_admin']),
            )
            for row in cur.fetchall()
        ]
    return jsonify({'users': users})


@app.route('/api/add_user', methods=['POST'])
@login_required
def api_add_user():
    """Add a new user.  Admin only.

    The request JSON must include ``username`` and ``password``.  Optional
    fields:

    - ``plan``: 'Free' or 'Pro' (default 'Free').
    - ``expires_at``: ISO date string for account expiration or ``null`` for
      unlimited access.  If provided, it must be a valid date string.
    - ``is_admin``: boolean flag; if ``true`` then the new user will have
      admin privileges.  Only an existing admin can set this flag.

    Returns the new user's id or an error.  Only admins may call this
    endpoint.
    """
    current = get_current_user()
    if not current or not current['is_admin']:
        return jsonify({'error': 'Forbidden'}), 403
    try:
        data = request.get_json(force=True) or {}
    except Exception:
        return jsonify({'error': 'Invalid request'}), 400
    username = data.get('username')
    password = data.get('password')
    plan = data.get('plan', 'Free')
    expires_at = data.get('expires_at')  # may be None or empty string
    is_admin_flag = bool(data.get('is_admin', False))
    # Validate required fields
    if not username or not password:
        return jsonify({'error': 'Missing username or password'}), 400
    # Validate expires_at if provided
    if expires_at:
        try:
            datetime.date.fromisoformat(expires_at)
        except Exception:
            return jsonify({'error': 'Invalid expires_at format'}), 400
    # Insert new user
    with get_db_connection() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO users (username, password, plan, expires_at, is_admin) VALUES (?, ?, ?, ?, ?)",
                (username, password, plan, expires_at if expires_at else None, 1 if is_admin_flag else 0),
            )
            conn.commit()
            new_id = cur.lastrowid
        except sqlite3.IntegrityError:
            return jsonify({'error': 'Username already exists'}), 400
    return jsonify({'success': True, 'user_id': new_id})


@app.route('/api/delete_user', methods=['POST'])
@login_required
def api_delete_user():
    """Delete a user by id.  Admin only.  Cannot delete oneself."""
    current = get_current_user()
    if not current or not current['is_admin']:
        return jsonify({'error': 'Forbidden'}), 403
    data = request.get_json(force=True) or {}
    user_id = data.get('user_id')
    if not user_id:
        return jsonify({'error': 'Missing user_id'}), 400
    if int(user_id) == current['id']:
        return jsonify({'error': 'Cannot delete yourself'}), 400
    with get_db_connection() as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.execute("DELETE FROM api_tokens WHERE user_id = ?", (user_id,))
        conn.commit()
    return jsonify({'success': True})


@app.route('/api/change_plan', methods=['POST'])
@login_required
def api_change_plan():
    """Change a user's plan.  Admin only."""
    current = get_current_user()
    if not current or not current['is_admin']:
        return jsonify({'error': 'Forbidden'}), 403
    data = request.get_json(force=True) or {}
    user_id = data.get('user_id')
    plan = data.get('plan')
    if not user_id or not plan:
        return jsonify({'error': 'Missing fields'}), 400
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE users SET plan = ? WHERE id = ?",
            (plan, user_id),
        )
        conn.commit()
    return jsonify({'success': True})


@app.route('/api/generate_token', methods=['POST'])
@login_required
def api_generate_token():
    """Generate a new API token for a user.  Admin only.

    The request body must include ``user_id`` identifying the user for whom
    the token should be generated.  Only admins may call this endpoint.
    """
    current = get_current_user()
    if not current or not current['is_admin']:
        return jsonify({'error': 'Forbidden'}), 403
    data = request.get_json(force=True) or {}
    user_id = data.get('user_id')
    if not user_id:
        return jsonify({'error': 'Missing user_id'}), 400
    token = secrets.token_hex(16)
    with get_db_connection() as conn:
        conn.execute(
            "INSERT INTO api_tokens (user_id, token) VALUES (?, ?)",
            (user_id, token),
        )
        conn.commit()
    return jsonify({'success': True, 'token': token})


# ------------------------
# Tokens page and account/settings pages
# ------------------------

@app.route('/tokens')
@login_required
def tokens_page():
    """Display the API tokens page.

    Only administrators are allowed to access this page.  If a non-admin
    user attempts to access it, a 403 error is returned.  For admins
    the page will show the tokens associated with the current admin
    account.  Token generation for other users should be performed via
    the Manage Users page.
    """
    user = get_current_user()
    # Only admins can view tokens page
    if not user or not user['is_admin']:
        abort(403)
    with get_db_connection() as conn:
        cur = conn.execute(
            "SELECT token FROM api_tokens WHERE user_id = ? ORDER BY created_at DESC",
            (user['id'],),
        )
        tokens = [row['token'] for row in cur.fetchall()]
    # Provide translations
    lang = get_current_language()
    t = TRANSLATIONS.get(lang, TRANSLATIONS['en'])
    return render_template('tokens.html', user=user, tokens=tokens, t=t)


@app.route('/account')
@login_required
def account_page():
    """Display account details for the current user."""
    user = get_current_user()
    # Provide translations
    lang = get_current_language()
    t = TRANSLATIONS.get(lang, TRANSLATIONS['en'])
    return render_template('account.html', user=user, t=t)


@app.route('/settings')
@login_required
def settings_page():
    """Display settings page (placeholder)."""
    user = get_current_user()
    # Provide translations
    lang = get_current_language()
    t = TRANSLATIONS.get(lang, TRANSLATIONS['en'])
    return render_template('settings.html', user=user, t=t)


@app.route('/api/export/csv')
@login_required
def api_export_csv():
    """Export the records to a CSV file.

    Accepts optional ``days`` query parameter to restrict the export to the
    last N days.  Returns a CSV file download.
    """
    days = request.args.get('days', default=None, type=int)
    query = "SELECT record_date, type, amount FROM records"
    params = []
    if days is not None:
        threshold = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
        query += " WHERE record_date >= ?"
        params.append(threshold)
    query += " ORDER BY record_date ASC, id ASC"
    with get_db_connection() as conn:
        cur = conn.execute(query, params)
        rows = cur.fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Date', 'Type', 'Amount'])
    for row in rows:
        writer.writerow([row['record_date'], row['type'], row['amount']])
    csv_data = output.getvalue()
    response = make_response(csv_data)
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = 'attachment; filename=records.csv'
    return response


@app.route('/api/export/excel')
@login_required
def api_export_excel():
    """Export the records to an Excel file (xlsx).

    Accepts optional ``days`` query parameter to restrict the export to the
    last N days.  Returns an Excel file download.
    """
    days = request.args.get('days', default=None, type=int)
    query = "SELECT record_date, type, amount FROM records"
    params = []
    if days is not None:
        threshold = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
        query += " WHERE record_date >= ?"
        params.append(threshold)
    query += " ORDER BY record_date ASC, id ASC"
    with get_db_connection() as conn:
        cur = conn.execute(query, params)
        rows = cur.fetchall()
    # Create workbook
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Records'
    ws.append(['Date', 'Type', 'Amount'])
    for row in rows:
        ws.append([row['record_date'], row['type'], row['amount']])
    # Save to BytesIO
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    response = make_response(buf.read())
    response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    response.headers['Content-Disposition'] = 'attachment; filename=records.xlsx'
    return response


# ------------------------
# Account and settings API endpoints
# ------------------------

@app.route('/api/change_password', methods=['POST'])
@login_required
def api_change_password():
    """Change the current user's password.

    Expects JSON body with ``new_password`` and ``confirm_password`` fields.
    Returns success status and a translated message on success/failure.
    """
    current = get_current_user()
    # Ensure user exists
    if not current:
        return jsonify({'success': False, 'error': 'Not authenticated.'}), 403
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({'success': False, 'error': 'Invalid request.'}), 400
    new_password = (data or {}).get('new_password')
    confirm_password = (data or {}).get('confirm_password')
    lang = get_current_language()
    t = TRANSLATIONS.get(lang, TRANSLATIONS['en'])
    # Basic validation
    if not new_password or not confirm_password or new_password != confirm_password:
        return jsonify({'success': False, 'error': t['password_change_error']}), 400
    # Update password in DB
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE users SET password = ? WHERE id = ?",
            (new_password, current['id']),
        )
        conn.commit()
    return jsonify({'success': True, 'message': t['password_change_success']})


@app.route('/api/change_username', methods=['POST'])
@login_required
def api_change_username():
    """Change the current user's username.

    Expects JSON body with ``new_username`` and optionally ``confirm_username``.
    If provided, ``new_username`` and ``confirm_username`` must match.
    Returns success status and a translated message on success or error.
    """
    current = get_current_user()
    if not current:
        return jsonify({'success': False, 'error': 'Not authenticated.'}), 403
    try:
        data = request.get_json(force=True) or {}
    except Exception:
        return jsonify({'success': False, 'error': 'Invalid request.'}), 400
    new_username = data.get('new_username')
    # If confirm_username not provided, assume matches new_username
    confirm_username = data.get('confirm_username', new_username)
    lang = get_current_language()
    t = TRANSLATIONS.get(lang, TRANSLATIONS['en'])
    # Validate input
    if not new_username or new_username != confirm_username:
        return jsonify({'success': False, 'error': t['username_change_error']}), 400
    # Ensure username is unique
    with get_db_connection() as conn:
        cur = conn.execute(
            "SELECT id FROM users WHERE username = ? AND id != ?",
            (new_username, current['id']),
        )
        row = cur.fetchone()
        if row:
            return jsonify({'success': False, 'error': 'Username already exists.'}), 400
        # Update username
        conn.execute(
            "UPDATE users SET username = ? WHERE id = ?",
            (new_username, current['id']),
        )
        conn.commit()
    return jsonify({'success': True, 'message': t['username_change_success']})


# ------------------------
# Date range and grouping endpoints
# ------------------------

@app.route('/api/summary_range')
@login_required
def api_summary_range() -> 'flask.Response':
    """Return summary statistics for a date range with optional grouping.

    Query parameters:
        ``start`` – ISO date string (YYYY‑MM‑DD) for the beginning of the range (inclusive).
        ``end`` – ISO date string (YYYY‑MM‑DD) for the end of the range (inclusive).
        ``group`` – one of 'daily', 'monthly', 'yearly' to aggregate by day, month or year (default: daily).

    The returned JSON includes an array of group objects and overall totals.  Each
    group object has keys ``period``, ``sales``, ``expenses`` and ``profit``.
    Only records belonging to the current user are considered.
    """
    start = request.args.get('start')
    end = request.args.get('end')
    group = request.args.get('group', 'daily')
    # Validate dates
    try:
        if start:
            datetime.date.fromisoformat(start)
        if end:
            datetime.date.fromisoformat(end)
    except Exception:
        return jsonify({'error': 'Invalid date format'}), 400
    # Determine current user
    current = get_current_user()
    user_id = current['id'] if current else None
    # Build SQL for grouping
    if group == 'yearly':
        group_expr = "substr(record_date, 1, 4)"  # YYYY
    elif group == 'monthly':
        group_expr = "substr(record_date, 1, 7)"  # YYYY-MM
    else:
        group = 'daily'
        group_expr = "record_date"  # YYYY-MM-DD
    # Build a query that aggregates sales, expenses and additional metrics
    # across the requested date range.  We count distinct sale records to
    # compute the number of orders and sum over sale_items for quantities,
    # discounts and gross values.  Records of type 'Expense' do not join to
    # sale_items.
    query = f"""
        SELECT {group_expr} AS period,
               IFNULL(SUM(CASE WHEN r.type='Sale' THEN r.amount ELSE 0 END), 0) AS sales,
               IFNULL(SUM(CASE WHEN r.type='Expense' THEN r.amount ELSE 0 END), 0) AS expenses,
               COUNT(DISTINCT CASE WHEN r.type='Sale' THEN r.id END) AS orders,
               IFNULL(SUM(CASE WHEN r.type='Sale' THEN si.quantity ELSE 0 END), 0) AS items,
               IFNULL(SUM(CASE WHEN r.type='Sale' THEN si.discount ELSE 0 END), 0) AS discount,
               IFNULL(SUM(CASE WHEN r.type='Sale' THEN si.price * si.quantity ELSE 0 END), 0) AS gross
        FROM records r
        LEFT JOIN sale_items si ON si.record_id = r.id
        WHERE r.user_id = ?
    """
    params = [user_id]
    where_clauses = []
    # Append date range conditions
    if start:
        where_clauses.append("r.record_date >= ?")
        params.append(start)
    if end:
        where_clauses.append("r.record_date <= ?")
        params.append(end)
    if where_clauses:
        query += " AND " + " AND ".join(where_clauses)
    query += f" GROUP BY period ORDER BY period ASC"
    groups = []
    # Execute query and accumulate totals
    total_sales = 0.0
    total_expenses = 0.0
    total_orders = 0
    total_items = 0
    total_discount = 0.0
    total_gross = 0.0
    with get_db_connection() as conn:
        cur = conn.execute(query, params)
        rows = cur.fetchall()
        for row in rows:
            sales = float(row['sales'] or 0)
            expenses = float(row['expenses'] or 0)
            orders = int(row['orders'] or 0)
            items = int(row['items'] or 0)
            disc = float(row['discount'] or 0)
            gross = float(row['gross'] or 0)
            profit = sales - expenses
            avg_sale = sales / orders if orders > 0 else 0
            total_sales += sales
            total_expenses += expenses
            total_orders += orders
            total_items += items
            total_discount += disc
            total_gross += gross
            groups.append({
                'period': row['period'],
                'sales': sales,
                'expenses': expenses,
                'profit': profit,
                'orders': orders,
                'items': items,
                'discount': disc,
                'gross': gross,
                'avg_sale': avg_sale,
            })
    total_profit = total_sales - total_expenses
    total_avg_sale = total_sales / total_orders if total_orders > 0 else 0
    totals = {
        'sales': total_sales,
        'expenses': total_expenses,
        'profit': total_profit,
        'orders': total_orders,
        'items': total_items,
        'discount': total_discount,
        'gross': total_gross,
        'avg_sale': total_avg_sale,
    }
    return jsonify({'group': group, 'groups': groups, 'totals': totals})


@app.route('/api/records_range')
@login_required
def api_records_range() -> 'flask.Response':
    """Return raw records for a date range.

    Query parameters:
        ``start`` – ISO date string (inclusive start of range).
        ``end`` – ISO date string (inclusive end of range).

    The returned JSON contains a list of record objects filtered by the
    current user and the date range.  Records are ordered by date
    descending then id descending.
    """
    start = request.args.get('start')
    end = request.args.get('end')
    try:
        if start:
            datetime.date.fromisoformat(start)
        if end:
            datetime.date.fromisoformat(end)
    except Exception:
        return jsonify({'error': 'Invalid date format'}), 400
    current = get_current_user()
    user_id = current['id'] if current else None
    query = "SELECT id, record_date, type, amount FROM records WHERE user_id = ?"
    params = [user_id]
    if start:
        query += " AND record_date >= ?"
        params.append(start)
    if end:
        query += " AND record_date <= ?"
        params.append(end)
    query += " ORDER BY record_date DESC, id DESC"
    with get_db_connection() as conn:
        cur = conn.execute(query, params)
        rows = cur.fetchall()
    records = []
    for r in rows:
        records.append({
            'id': r['id'],
            'record_date': r['record_date'],
            'type': r['type'],
            'amount': float(r['amount']),
        })
    return jsonify({'records': records})




if __name__ == '__main__':
    # Only run the development server when executed directly.  Host and port
    # remain default; override via environment variables as needed.  Do not
    # use this built‑in server in production.
    app.run(debug=True)