# Smart Expense Tracker

A web app to track expenses, set budgets, and view spending insights.

## Features

- User registration and login
- Add income and expenses with categories
- Budget tracking and alerts
- Charts, history, search, and analysis
- Responsive dashboard (desktop and mobile)

## Tech Stack

- Python / Flask
- MySQL (production) or SQLite (local dev)
- HTML, CSS, Font Awesome

## Local Setup

```bash
git clone https://github.com/Eliyabujilima/smart-expense-tracker.git
cd smart-expense-tracker
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`

For local dev, leave `DATABASE_URL` unset to use SQLite (`expenses.db`).

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Production | `mysql://user:pass@host:port/dbname` |
| `SECRET_KEY` | Production | Random secret for Flask sessions |
| `FLASK_DEBUG` | Optional | `1` for local dev, `0` for production |

## Deploy (Recommended Free Stack)

**App:** [Render](https://render.com) (free web service)  
**Database:** [TiDB Cloud Serverless](https://tidbcloud.com) (free MySQL-compatible)

Vercel is not recommended for this Flask app — it is built for static/Next.js sites, not Python backends.

See [DEPLOY.md](DEPLOY.md) for step-by-step hosting instructions.

## Author

Eliya Bujilima
