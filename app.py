from flask import Flask, render_template, request, redirect, session
from db import get_db_connection
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import uuid
import os
import logging

# IMPORT ANALYTICS
from analytics.engine import *

app = Flask(__name__)

# --- Secret / session handling ---
# Require a SECRET_KEY in production to avoid session invalidation after restarts.
secret = os.getenv("SECRET_KEY")
flask_debug = os.getenv("FLASK_DEBUG", "0") == "1"

if not secret and not flask_debug:
    # Fail fast in production so deployments clearly show the missing secret.
    raise RuntimeError("Missing SECRET_KEY environment variable. Set SECRET_KEY for production deployments.")

# Use a development-only fallback when FLASK_DEBUG=1 so local development works without env vars.
app.secret_key = secret or "dev_only_secret_for_local_testing"

# Sessions: keep users logged in for 30 days by default and refresh expiry on each request
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)
app.config["SESSION_REFRESH_EACH_REQUEST"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_HTTPONLY"] = True
# In production (non-debug), require secure cookies (HTTPS)
app.config["SESSION_COOKIE_SECURE"] = not flask_debug

# Optional: attempt to enable server-side sessions if Flask-Session and redis are available
# This is useful for multi-instance deployments or when you want sessions to survive app restarts.
redis_url = os.getenv("REDIS_URL")
if redis_url:
    try:
        from flask_session import Session
        import redis

        app.config["SESSION_TYPE"] = "redis"
        app.config["SESSION_REDIS"] = redis.from_url(redis_url)
        Session(app)
        logging.info("Flask-Session enabled using REDIS_URL")
    except Exception as e:
        # If Flask-Session/redis are not installed or misconfigured, we don't fail the app.
        logging.warning("Flask-Session not configured (missing package or invalid REDIS_URL): %s", e)

# Initialize database
def init_db():
    conn, is_mysql = get_db_connection()
    if conn is None:
        return
    cursor = conn.cursor(dictionary=True) if is_mysql else conn.cursor()
    if is_mysql:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(255) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                type VARCHAR(255) NOT NULL,
                name VARCHAR(255) NOT NULL,
                amount DECIMAL(10,2) NOT NULL,
                category VARCHAR(255) NOT NULL,
                date DATE NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS budgets (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                category VARCHAR(255) NOT NULL,
                amount DECIMAL(10,2) NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) UNIQUE NOT NULL
            )
        ''')
    else:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                type TEXT NOT NULL,
                name TEXT NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                date DATE NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS budgets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                amount REAL NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            )
        ''')
    conn.commit()
    # Insert default categories if not exist
    if is_mysql:
        cursor.execute("INSERT IGNORE INTO categories (name) VALUES ('Food'), ('Transport'), ('Entertainment'), ('Utilities'), ('Other')")
    else:
        cursor.execute("INSERT OR IGNORE INTO categories (name) VALUES ('Food'), ('Transport'), ('Entertainment'), ('Utilities'), ('Other')")
    conn.commit()
    conn.close()

init_db()

# ----------------------
# HELPER
# ----------------------
def safe_date(date_val):
    if isinstance(date_val, str):
        return date_val
    return date_val.strftime("%Y-%m-%d")

def get_category_names(rows):
    return [r["name"] if isinstance(r, dict) else r[0] for r in rows]

def insert_category_ignore(cursor, is_mysql, category):
    if is_mysql:
        cursor.execute("INSERT IGNORE INTO categories (name) VALUES (?)", (category,))
    else:
        cursor.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (category,))

def monthly_trend(transactions):
    trend = {}

    for t in transactions:
        if t["type"] == "expense":
            date_val = t["date"]

            if isinstance(date_val, str):
                month = date_val[:7]   # YYYY-MM
            else:
                month = date_val.strftime("%Y-%m")

            trend[month] = trend.get(month, 0) + t["amount"]

    return trend

# ----------------------
# HOME
# ----------------------
@app.route("/")
def home():
    print("HOME ROUTE START")
    if "user_id" not in session:
        return redirect("/welcome")

    conn, _ = get_db_connection()
    cursor = conn.cursor(dictionary=True) if _ else conn.cursor()

    cursor.execute("SELECT * FROM transactions WHERE user_id=?", (session["user_id"],))
    transactions = cursor.fetchall()

    cursor.execute(
            "SELECT * FROM budgets WHERE user_id= ?",
            (session["user_id"],)
        )

    budgets_data = cursor.fetchall()

        # 🔥 FIX: normalize categories
    budgets = {
            b["category"].strip().title(): b["amount"]
            for b in budgets_data
        }
    conn.close()
    
    income = total_income(transactions)
    expense = total_expense(transactions)
    balance = current_balance(transactions)
    
    hour = datetime.now().hour

    if hour < 12:
        greeting = "GOOD MORNING"
    elif hour < 18:
        greeting = "GOOD AFTERNOON"
    else:
        greeting = "GOOD EVENING"   
    today_total = today_spending(transactions)
    weekly = weekly_spending(transactions)
    monthly = monthly_spending(transactions)
    yearly = yearly_spending(transactions)

    insights = generate_insights(transactions)
    budget_insights = budget_intelligence(transactions, budgets)
    trend_data = monthly_trend(transactions)
    budget_data = budget_usage(transactions, budgets)
    
    username = session.get("username")
    
    print("HOME ROUTE END")
    return render_template(
        "index.html",
        transactions=[t for t in transactions if safe_date(t["date"]) == datetime.now().strftime("%Y-%m-%d")],
        income=income,
        expense=expense,
        balance=balance,
        today_total=today_total,
        weekly=weekly,
        monthly=monthly,
        yearly=yearly,
        chart_data=category_chart_data(transactions),
        budgets=budgets,
        totals=category_spending(transactions),
        warnings=budget_warnings(transactions, budgets),
        insights=insights,
        trend_data=trend_data,
        budget_insights=budget_insights,
        username=username,
        greeting=greeting,
        budget_data=budget_data

    )
    
# ----------------------
# ADD EXPENSE
# ----------------------
@app.route("/add", methods=["GET", "POST"])
def add():
    if "user_id" not in session:
        return redirect("/login")

    conn, is_mysql = get_db_connection()
    cursor = conn.cursor(dictionary=True) if is_mysql else conn.cursor()

    cursor.execute("SELECT name FROM categories")
    categories = get_category_names(cursor.fetchall())

    if request.method == "POST":
        try:
            name = request.form["name"]

            category = request.form.get("category")
            if category == "__new__":
                category = request.form.get("new_category")
                insert_category_ignore(cursor, is_mysql, category)

            if not category:
                category = "Other"

            amount = float(request.form.get("amount", 0) or 0)

            # Check if this is an edit operation
            edit_id = request.form.get("edit_id")
            if edit_id:
                # Update existing transaction
                cursor.execute(
                    "UPDATE transactions SET name=?, amount=?, category=? WHERE id=? AND user_id=?",
                    (name, amount, category, edit_id, session["user_id"])
                )
            else:
                # Insert new transaction
                date = datetime.now().strftime("%Y-%m-%d")
                cursor.execute("""
                    INSERT INTO transactions (type, name, amount, category, date, user_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, ("expense", name, amount, category, date, session["user_id"]))

            conn.commit()

        except Exception as e:
            print("ERROR:", e)

        finally:
            conn.close()

        return redirect("/")

    conn.close()
    return render_template("add.html", categories=categories)

# ----------------------
# ADD INCOME
# ----------------------
@app.route("/add_income", methods=["GET", "POST"])
def add_income():
    if "user_id" not in session:
        return redirect("/login")

    if request.method == "POST":
        try:
            conn, _ = get_db_connection()
            cursor = conn.cursor(dictionary=True) if _ else conn.cursor()

            name = request.form["name"]
            amount = float(request.form.get("amount", 0) or 0)
            date = datetime.now().strftime("%Y-%m-%d")

            cursor.execute("""
                INSERT INTO transactions (type, name, amount, category, date, user_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, ("income", name, amount, "Income", date, session["user_id"]))

            conn.commit()

        except Exception as e:
            print("ERROR:", e)

        finally:
            conn.close()

        return redirect("/")

    return render_template("add_income.html")

# ----------------------
# DELETE
# ----------------------
@app.route("/delete/<id>")
def delete(id):
    if "user_id" not in session:
        return redirect("/login")

    conn, _ = get_db_connection()
    cursor = conn.cursor(dictionary=True) if _ else conn.cursor()

    cursor.execute(
        "DELETE FROM transactions WHERE id=? AND user_id=?",
        (id, session["user_id"])
    )

    conn.commit()
    conn.close()

    return redirect("/history")

# ----------------------
# EDIT
# ----------------------
@app.route("/edit/<id>")
def edit(id):
    if "user_id" not in session:
        return redirect("/login")

    conn, _ = get_db_connection()
    cursor = conn.cursor(dictionary=True) if _ else conn.cursor()

    cursor.execute("SELECT * FROM transactions WHERE id=? AND user_id=?", (id, session["user_id"]))
    transaction = cursor.fetchone()

    conn.close()

    if transaction:
        # Redirect to add page with transaction data as query parameters
        return redirect(f"/add?edit_id={transaction['id']}&name={transaction['name']}&amount={transaction['amount']}&category={transaction['category']}")
    else:
        return redirect("/")

@app.route('/welcome')
def welcome():
    if "user_id" in session:
        return redirect("/")
    return render_template('welcome.html')

# ----------------------
# RANGE ANALYSIS
# ----------------------
@app.route("/range", methods=["GET", "POST"])
def range_analysis():
    if "user_id" not in session:
        return redirect("/login")

    total = 0
    results = []

    if request.method == "POST":
        conn, _ = get_db_connection()
        cursor = conn.cursor(dictionary=True) if _ else conn.cursor()
        cursor.execute("SELECT * FROM transactions WHERE user_id=?", (session["user_id"],))
        transactions = cursor.fetchall()
        conn.close()

        total, results = spending_by_range(
            transactions,
            request.form["start"],
            request.form["end"]
        )

    return render_template("range.html", total=total, results=results)

# ----------------------
# SEARCH
# ----------------------
@app.route("/search", methods=["GET", "POST"])
def search():
    if "user_id" not in session:
        return redirect("/login")

    total = 0
    expenses = []

    if request.method == "POST":
        conn, _ = get_db_connection()
        cursor = conn.cursor(dictionary=True) if _ else conn.cursor()
        date = request.form["date"]
        cursor.execute(
            "SELECT * FROM transactions WHERE user_id=? AND date=? AND type='expense'",
            (session["user_id"], date)
        )
        expenses = cursor.fetchall()
        conn.close()
        total = sum(e["amount"] for e in expenses)

    return render_template("search.html", total=total, expenses=expenses)

# ----------------------
# HISTORY
# ----------------------
@app.route("/history")
def history():
    if "user_id" not in session:
        return redirect("/login")

    conn, _ = get_db_connection()
    cursor = conn.cursor(dictionary=True) if _ else conn.cursor()

    cursor.execute("SELECT * FROM transactions WHERE user_id=? ORDER BY date DESC", (session["user_id"],))
    all_transactions = cursor.fetchall()

    conn.close()

    period = request.args.get('period', 'all')
    now = datetime.now()

    if period == 'today':
        transactions = [t for t in all_transactions if datetime.strptime(t['date'], '%Y-%m-%d').date() == now.date()]
    elif period == 'week':
        start_of_week = now - timedelta(days=now.weekday())
        transactions = [t for t in all_transactions if datetime.strptime(t['date'], '%Y-%m-%d').date() >= start_of_week.date()]
    elif period == 'month':
        start_of_month = now.replace(day=1)
        transactions = [t for t in all_transactions if datetime.strptime(t['date'], '%Y-%m-%d').date() >= start_of_month.date()]
    elif period == 'year':
        start_of_year = now.replace(month=1, day=1)
        transactions = [t for t in all_transactions if datetime.strptime(t['date'], '%Y-%m-%d').date() >= start_of_year.date()]
    else:
        transactions = all_transactions

    return render_template("history.html", transactions=transactions, period=period)

# ----------------------
# SET BUDGET
# ----------------------
@app.route("/set-budget", methods=["GET", "POST"])
def set_budget():
    if "user_id" not in session:
        return redirect("/login")

    conn, is_mysql = get_db_connection()
    cursor = conn.cursor(dictionary=True) if is_mysql else conn.cursor()

    cursor.execute("SELECT name FROM categories")
    categories = get_category_names(cursor.fetchall())

    if request.method == "POST":

        category = request.form.get("category")

        if category == "__new__":
            category = request.form.get("new_category")

        if not category or category.strip() == "":
            category = "Other"

        # 🔥 FIX: normalize category
        category = category.strip().title()

        amount = float(request.form.get("amount", 0))

        # 🔥 FIX: FORCE UPDATE PER USER
        cursor.execute("""
            DELETE FROM budgets
            WHERE user_id=? AND category=?
        """, (session["user_id"], category))

        cursor.execute("""
            INSERT INTO budgets (user_id, category, amount)
            VALUES (?, ?, ?)
        """, (session["user_id"], category, amount))

        conn.commit()
        conn.close()

        return redirect("/")

    conn.close()
    return render_template("set_budget.html", categories=categories)
# ----------------------
# AUTH
# ----------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    if request.method == "POST":
        conn, _ = get_db_connection()
        cursor = conn.cursor(dictionary=True) if _ else conn.cursor()

        username = request.form["username"]
        password = generate_password_hash(request.form["password"])

        cursor.execute("SELECT * FROM users WHERE username=?", (username,))
        existing_user = cursor.fetchone()

        if existing_user:
            conn.close()
            error = "Username already exists. Please choose another."
            return render_template("register.html", error=error)

        cursor.execute("""
            INSERT INTO users (username, password)
            VALUES (?, ?)
        """, (username, password))

        conn.commit()
        conn.close()

        return redirect("/login")

    return render_template("register.html", error=error)

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        conn, _ = get_db_connection()
        cursor = conn.cursor(dictionary=True) if _ else conn.cursor()

        username = request.form["username"]
        password = request.form["password"]

        cursor.execute("SELECT * FROM users WHERE username=?", (username,))
        user = cursor.fetchone()

        conn.close()

        if user and check_password_hash(user["password"], password):
            session.permanent = True
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect("/")
        else:
            error = "Invalid username or password. Please try again."

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/welcome")

#    calculator route
@app.route('/calculator')
def calculator():
    return render_template('calculator.html')

#   help route
@app.route('/help')
def help_page():
    return render_template('help.html')

# ----------------------
# CHARTS
# ----------------------
@app.route('/charts')
def charts():
    if "user_id" not in session:
        return redirect("/login")

    conn, _ = get_db_connection()
    cursor = conn.cursor(dictionary=True) if _ else conn.cursor()

    cursor.execute("SELECT * FROM transactions WHERE user_id=?", (session["user_id"],))
    transactions = cursor.fetchall()

    cursor.execute(
        "SELECT * FROM budgets WHERE user_id=?",
        (session["user_id"],)
    )

    budgets_data = cursor.fetchall()

    budgets = {
        b["category"].strip().title(): b["amount"]
        for b in budgets_data
    }
    conn.close()

    income = total_income(transactions)
    expense = total_expense(transactions)
    trend_data = monthly_trend(transactions)
    budget_data = budget_usage(transactions, budgets)
    chart_data = category_chart_data(transactions)

    return render_template('charts.html', income=income, expense=expense, trend_data=trend_data, budget_data=budget_data, chart_data=chart_data)

# ----------------------
# EXPORT
# ----------------------
@app.route('/export')
def export():
    if "user_id" not in session:
        return redirect("/login")

    conn, _ = get_db_connection()
    cursor = conn.cursor(dictionary=True) if _ else conn.cursor()

    cursor.execute("SELECT * FROM transactions WHERE user_id=? ORDER BY date DESC", (session["user_id"],))
    transactions = cursor.fetchall()
    conn.close()

    import csv
    from io import StringIO

    si = StringIO()
    writer = csv.writer(si)
    writer.writerow(['Type', 'Name', 'Amount', 'Category', 'Date'])

    for t in transactions:
        writer.writerow([t['type'], t['name'], t['amount'], t['category'], t['date']])

    output = si.getvalue()
    si.close()

    from flask import Response
    return Response(output, mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename=transactions.csv'})

# ----------------------
# ERRORS

# ----------------------
@app.errorhandler(500)
def internal_error(e):
    return render_template("error.html"), 500

@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404

# ----------------------
# RUN
# ----------------------
if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "1") == "1"
    app.run(host="0.0.0.0", port=5000, debug=debug, use_reloader=debug)
