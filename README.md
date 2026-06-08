# Project Solace

Project Solace is a self-hosted household set-aside planner for recurring bills, planned purchases, income sources, and bucket-based payday transfers.

It is intentionally not a full transaction-tracking budget app. Its main job is to answer: **how much should each person transfer into each bucket this pay cycle?**

## Current feature set

- Recurring bills
- Planned purchases
- Fortnightly pay-cycle calculations
- Income sources by person
- Bucket allocations by percentage or fixed household amount
- Per-person contribution breakdowns
- Calendar and list views for monthly bills/income
- Modular dashboard
- Payday checklist
- Bills bucket health indicator
- Import preview for recurring bills
- Backup and restore page
- Audit log
- Notification settings scaffold
- Dark mode
- Docker deployment

## Local development

```bash
cd project-solace
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

Open:

```text
http://localhost:5000
```

Default development login:

```text
Username: admin
Password: admin
```

## Docker

```bash
cp .env.example .env
nano .env
docker compose up -d --build
```

Open:

```text
http://localhost:5055
```

## Backups

Use **Manage → Backup & Restore** before applying updates. The SQLite database ZIP is the restore-capable backup. CSV/XLSX exports are useful for review, but the database ZIP is the full backup.

## Server stability defaults

The Docker build is configured for small household self-hosting with SQLite:

- Gunicorn: `1` worker, `4` threads, `60` second timeout.
- SQLite WAL mode and a `30` second busy timeout are enabled at app startup.
- Startup database setup is serialised with an instance-folder lock file.
- Docker Compose mounts `./instance:/app/instance:Z` for Fedora/SELinux compatibility.

These defaults are intended to support multiple household users at once without turning the app into a heavier PostgreSQL deployment.
