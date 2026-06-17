# Deployment Guide — Free Hosting until Demo (Dec 2026)

## Quick answer

| Platform | Good for this app? | Why |
|----------|-------------------|-----|
| **Render** | Yes | Runs Flask + gunicorn on free tier |
| **Vercel** | No | Not meant for full Flask apps; no always-on Python server |
| **Railway** | Was good | Now needs paid credits for MySQL |
| **TiDB Cloud** | Yes (DB) | Free MySQL-compatible database |

### Can free tiers handle many users?

| Scale | Free tier OK? |
|-------|---------------|
| Demo to friends (5–30 people) | Yes |
| Class presentation / portfolio | Yes |
| 50–100 occasional users | Maybe (slow cold starts on Render) |
| Hundreds concurrent users | No — need paid plan |

**Render free limitation:** App sleeps after ~15 min with no traffic. First visit takes 30–60 seconds to wake up. Data stays in MySQL (TiDB), not lost.

---

## Step 1 — Push to GitHub

Already connected to:
`https://github.com/Eliyabujilima/smart-expense-tracker`

---

## Step 2 — Create free MySQL database (TiDB Cloud)

1. Go to [https://tidbcloud.com](https://tidbcloud.com) and sign up (free).
2. Create a **Serverless** cluster (free tier).
3. Create database e.g. `expense_tracker`.
4. Get connection details and build `DATABASE_URL`:

```
mysql://USERNAME:PASSWORD@HOST:4000/expense_tracker
```

TiDB uses port **4000** (not 3306). Your `db.py` already supports `mysql://` URLs.

---

## Step 3 — Deploy app on Render

1. Go to [https://render.com](https://render.com) → Sign up with GitHub.
2. **New → Web Service** → connect `smart-expense-tracker` repo.
3. Settings:
   - **Runtime:** Python 3
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `gunicorn app:app --bind 0.0.0.0:$PORT`
   - **Plan:** Free
4. **Environment variables:**

| Key | Value |
|-----|-------|
| `DATABASE_URL` | Your TiDB connection string |
| `SECRET_KEY` | Random long string (e.g. from password generator) |
| `FLASK_DEBUG` | `0` |

5. Click **Deploy**. Wait 5–10 minutes.

Your app URL will be like: `https://smart-expense-tracker.onrender.com`

Tables are created automatically on first run (`init_db()` in `app.py`).

---

## Step 4 — Keep app awake (optional)

Render free sleeps when idle. Options:

- Accept slow first load (fine for demo).
- Use [UptimeRobot](https://uptimerobot.com) (free) to ping your URL every 5 minutes.

---

## Do NOT use Vercel for this project

Vercel does not host traditional Flask apps well. You would need to rewrite as serverless functions or split frontend/backend. **Use Render only** for the Python app.

---

## If TiDB does not work

Alternative free databases:

| Service | Type | Notes |
|---------|------|-------|
| **Neon** | PostgreSQL | Free, but needs small code changes (not MySQL) |
| **Supabase** | PostgreSQL | Free tier, same — not MySQL |
| **Aiven** | MySQL | Free trial only (~30 days) |

Staying on MySQL without code changes → **TiDB Cloud Serverless** is the best free option for your demo.

---

## Security reminder

- Never commit `.env` or database passwords to GitHub.
- Rotate your old Railway password if it was ever committed.
- Set a strong `SECRET_KEY` on Render.
