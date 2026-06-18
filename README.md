# Project Solace

> A self-hosted household finance planner for pay-cycle budgeting, recurring bills, and bucket-based transfers.

**Current release: 0.27.0-beta**

Project Solace helps households answer one question each pay cycle:

**How much should each person set aside for bills, savings, and spending buckets?**

It is not a transaction tracker, bank importer, or full accounting app. It is a lightweight planning tool built for households where two or more people have separate incomes and want a simple, shared view of what needs to be transferred and when.

---

## What it does

- Tracks recurring bills and their pay-cycle due dates
- Models income sources per person (weekly or fortnightly), including shared household income
- Calculates how much each person should transfer into each budget bucket each pay cycle
- Shows a payday checklist of transfers to complete
- Tracks planned purchases (shared and individual)
- Provides a calendar view of upcoming bills and income dates
- Supports cycle closeout, cycle history, and an annual summary

## What it is not

Project Solace is deliberately not:

- A bank transaction importer
- A full double-entry accounting system
- A replacement for apps like YNAB, Actual Budget, or a bank ledger

---

## Screenshots

*Coming soon.*

---

## Tech stack

- Python / Flask
- SQLite (via Flask-SQLAlchemy)
- Gunicorn
- Docker / Docker Compose
- Jinja2 templates
- Vanilla CSS and JS (no frontend framework)

---

## Requirements

- Docker and Docker Compose (recommended), **or**
- Python 3.10+

---

## Quick start with Docker

This is the recommended way to run Project Solace.

**Linux / macOS:**

```bash
git clone https://github.com/Moose151/project-solace.git
cd project-solace
cp .env.example .env
```

Edit `.env` with your chosen credentials and a strong secret key (see [Configuration](#configuration) below), then:

```bash
docker compose up -d --build
```

Open [http://localhost:5055](http://localhost:5055) in your browser and log in with the credentials you set in `.env`.

**Windows:**

Install [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/) and ensure it is running, then open PowerShell:

```powershell
git clone https://github.com/Moose151/project-solace.git
cd project-solace
copy .env.example .env
notepad .env
docker compose up -d --build
```

Open [http://localhost:5055](http://localhost:5055).

To stop the container:

```powershell
docker compose down
```

> **Note:** On Windows, Docker Desktop uses WSL 2 by default. The `:Z` volume label in `docker-compose.yml` is silently ignored on Windows — this is safe.

---

## Local development

### Linux / macOS

Install prerequisites (Ubuntu/Debian):

```bash
sudo apt update && sudo apt install git python3 python3-pip python3-venv
```

Set up the project:

```bash
git clone https://github.com/Moose151/project-solace.git
cd project-solace
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` for local development (see [Configuration](#configuration)), then run:

```bash
python run.py
```

Open [http://localhost:5000](http://localhost:5000).

### Windows

Install [Python 3](https://www.python.org/downloads/windows/) (tick **Add Python to PATH** during setup) and [Git for Windows](https://git-scm.com/download/win).

Open **Command Prompt** or **PowerShell**:

```bat
git clone https://github.com/Moose151/project-solace.git
cd project-solace
python -m venv .venv
.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
notepad .env
```

Run:

```bat
python run.py
```

Open [http://localhost:5000](http://localhost:5000).

To deactivate the virtual environment when done:

```bat
.venv\Scripts\deactivate
```

---

## Configuration

Copy `.env.example` to `.env` and fill in the values. The real `.env` is gitignored and must never be committed.

| Variable | Required | Description |
|---|---|---|
| `FLASK_SECRET_KEY` | Yes | Random string used to sign sessions. Generate one with `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `SOLACE_ADMIN_USERNAME` | Yes | Username for the initial admin account |
| `SOLACE_ADMIN_PASSWORD` | Yes | Password / PIN for the initial admin account |
| `DATABASE_URL` | Yes | `sqlite:////app/instance/solace.db` for Docker · `sqlite:///instance/solace.db` for local dev |
| `FLASK_DEBUG` | No | `true` for local dev · `false` (default) for production |

**Example `.env` for Docker / production:**

```env
FLASK_SECRET_KEY=replace-with-a-long-random-string
SOLACE_ADMIN_USERNAME=admin
SOLACE_ADMIN_PASSWORD=your-strong-password
DATABASE_URL=sqlite:////app/instance/solace.db
FLASK_DEBUG=false
```

**Example `.env` for local development:**

```env
FLASK_SECRET_KEY=local-dev-secret
SOLACE_ADMIN_USERNAME=admin
SOLACE_ADMIN_PASSWORD=admin
DATABASE_URL=sqlite:///instance/solace.db
FLASK_DEBUG=true
```

---

## Updating

Back up your data before updating (see [Backups](#backups)).

```bash
git pull origin main
docker compose down
docker compose build --no-cache
docker compose up -d
```

If the container runs as a non-root user and you see permission errors on the `instance/` folder:

```bash
sudo chown -R 1000:1000 instance
```

Confirm the running version at `/system-info` after restarting.

---

## SELinux hosts (Fedora / RHEL)

The `docker-compose.yml` volume mount includes `:Z` for SELinux relabelling:

```yaml
./instance:/app/instance:Z
```

This is required on Fedora and RHEL hosts. Do not remove it on SELinux-enforcing systems.

---

## Backups

Use **Manage → Backup & Restore** in the app before applying updates.

- The **SQLite database ZIP** is the full, restore-capable backup.
- XLSX / CSV exports are useful for review but cannot restore the database.

To back up the database directly on the host:

```bash
tar -czf solace-backup-$(date +%F).tar.gz instance
```

---

## Features

### Users

- Avatar and PIN login — users tap their card then enter a PIN
- Per-user display name and emoji avatar
- User management at **Manage → Users**

### Bills and income

- Recurring bills with frequencies: weekly, fortnightly, monthly, quarterly, six-monthly, yearly
- Optional stop-after date, autopay flag, category, account, and notes per bill
- Income sources per person (weekly or fortnightly)
- Shared household income with three allocation modes: standard pool, lump sum to a bucket, or custom per-bucket split
- "Known pay date" anchor — no manual updates needed each fortnight

### Pay-cycle planning

- Budget buckets by percentage or fixed amount, with remainder/cap and rounding increment
- Per-person contribution breakdown each cycle
- Weekly and fortnightly pay-cycle support
- Current and next cycle preview
- Payday checklist with transfer items, income confirmation, and hide/restore
- Cycle closeout with actual income tracking
- Cycle history (Planning → Cycle History)
- Annual / financial year summary (Planning → Annual Summary)
- Per-category budget envelopes with over/under indicator

### Dashboard

- Modular dashboard with configurable widget layout (Manage → Dashboard Layout)
- Widgets: cycle summary, bills due this cycle, bucket summaries, per-person contributions, planned purchases, payday checklist preview, overdue bills, bills bucket health, account balance snapshot, recurring totals, savings goals
- Mark bills paid or skipped directly from the dashboard without a page reload

### Calendar

- Month grid, list, and mobile agenda views
- Agenda grouped by Today / This Week / Coming Up / Past
- Overdue unpaid bills highlighted above the calendar
- Quick-add link on desktop day cells to pre-fill the bill form date

### Planned purchases

- Shared purchases funded by the household
- Individual purchases funded by a specific person's allocation
- Savings goals widget with progress bars and weeks-to-target

### Tools and admin

- Privacy filter — blurs money values on screen (stored in browser local storage)
- Live bill search and filter
- Bill detail page with audit log of amount changes
- Health check page (Manage → Health Check)
- System info / diagnostics page (Manage → System Info)
- Backup and restore with import preview
- XLSX and ZIP export
- Push notifications via ntfy / Gotify (test send)
- Dark mode
- Mobile-optimised UI throughout

---

## Server stability

The Docker build is configured for small self-hosted deployments with SQLite:

- Gunicorn: 1 worker, 4 threads, 60-second timeout
- SQLite WAL mode and 30-second busy timeout enabled at startup
- Startup seeding is serialised with a lock file to prevent race conditions
- Container runs as a non-root user

One worker is used intentionally — multiple workers can cause SQLite race conditions during the initial admin account seed.

---

## License

Project Solace is personal/hobbyist software shared publicly. No formal license is currently attached. If you intend to fork or redistribute it, please open an issue to discuss.
