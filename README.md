# Project Solace

Project Solace is a small self-hosted set-aside planner for recurring bills and planned purchases.

It is intentionally not a full budgeting app. It does not import bank transactions, reconcile accounts, or require every purchase to be entered.

The main question it answers is:

> How much money do we need to put aside this fortnight?

## Features

- Login
- Dashboard
- Recurring bills
- Generated bill occurrences
- Monthly bill view
- Pay-cycle view
- Planned purchases and savings targets
- Quick-add saved amounts
- Paid / unpaid / skipped bill status
- Categories
- Household settings
- Optional bills account balance snapshots
- CSV/XLSX import for recurring bills
- CSV export for bills and planned purchases
- XLSX readable backup
- SQLite database ZIP backup
- Light/dark theme setting
- Docker Compose deployment
- Health check endpoint at `/health`

## Tech stack

- Flask
- Flask-SQLAlchemy
- Flask-Login
- Flask-WTF
- SQLite
- Bootstrap 5
- Gunicorn
- Docker Compose

## Local development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

Open:

```text
http://localhost:5000
```

Default local login if no database exists:

```text
Username: admin
Password: admin
```

For real use, set your admin credentials through environment variables before the first database is created.

## Docker deployment

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env`:

```bash
nano .env
```

Change at least:

```env
FLASK_SECRET_KEY=change-this-to-a-long-random-string
SOLACE_ADMIN_USERNAME=admin
SOLACE_ADMIN_PASSWORD=change-this-password
SOLACE_PORT=5055
```

Start the app:

```bash
mkdir -p instance
docker compose up -d --build
```

Open:

```text
http://localhost:5055
```

The SQLite database is stored in:

```text
instance/solace.db
```

Do not delete the `instance/` folder unless you want to reset the app.

## GitHub/server deployment

See:

```text
docs/GITHUB_SETUP.md
docs/SERVER_DEPLOYMENT.md
```

Server update command after initial deployment:

```bash
./scripts/deploy.sh
```

Manual database backup:

```bash
./scripts/backup-db.sh
```

## Import bills

Go to **Data** and upload a CSV or XLSX file.

Supported recurring bill columns:

```text
name
amount
frequency
due_day
due_month
start_date
end_date
category
active
autopay
account_name
include_in_set_aside
notes
```

Minimal CSV example:

```csv
name,amount,frequency,due_day,start_date,category
Internet,89,Monthly,8,2026-01-01,Utilities
Car Rego,950,Yearly,20,2026-01-01,Vehicle
```

Australian dates such as `08/06/2026` are accepted.

## Backups

Use **Data → Download SQLite database ZIP** for a full backup.

Use the CSV/XLSX exports when you want readable data outside the app.

The database file itself is intentionally excluded from Git by `.gitignore`.

## Updating an existing local copy

For the current early stage, the simplest update path is:

1. Stop Flask or Docker Compose.
2. Back up `instance/solace.db`.
3. Pull the new code from GitHub or replace the app files.
4. Restart Flask or Docker Compose.

The app includes lightweight SQLite migrations for small schema changes.
