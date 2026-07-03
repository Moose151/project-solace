# Project Solace

> A self-hosted household finance planner for pay-cycle budgeting, recurring bills, and bucket-based transfers.

**Current release: 0.28.0-beta**

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
- Forecasts the bills account balance day by day and warns when a future bill won't be covered
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

## Deploying with Docker

Docker is the recommended way to run Project Solace. Your data is stored in a Docker named volume (`solace-data`) that is completely separate from the container. Restarting, rebuilding, or updating the container does not affect your data.

### Before you start — set up your `.env` file

The `.env` file must be created before you start the container for the first time. It sets the admin account credentials and a secret key used to secure sessions.

```bash
cp .env.example .env
```

Then open `.env` in a text editor and set these values:

```env
FLASK_SECRET_KEY=replace-with-a-long-random-string
SOLACE_ADMIN_USERNAME=admin
SOLACE_ADMIN_PASSWORD=your-chosen-pin
SOLACE_ADMIN_DISPLAY_NAME=Your Name
DATABASE_URL=sqlite:////app/instance/solace.db
FLASK_DEBUG=false
```

> **Important:** Set these values **before** running the container for the first time. The admin account is seeded from these values on first start. After that, you can change your display name and PIN from within the app — but the `.env` values are what get used if the database ever needs to be rebuilt from scratch.

To generate a strong secret key:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

---

### Linux

Install Docker if you haven't already:

```bash
sudo apt update && sudo apt install docker.io docker-compose-plugin
sudo usermod -aG docker $USER   # then log out and back in
```

Clone and start the app:

```bash
git clone https://github.com/Moose151/project-solace.git
cd project-solace
cp .env.example .env
nano .env        # or use any text editor
docker compose up -d --build
```

Open [http://localhost:5055](http://localhost:5055) and log in with the display name and PIN you set in `.env`.

---

### macOS

Install [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop/), open it, and wait until it shows "Docker Desktop is running."

```bash
git clone https://github.com/Moose151/project-solace.git
cd project-solace
cp .env.example .env
open -e .env     # opens in TextEdit — or use any editor
docker compose up -d --build
```

Open [http://localhost:5055](http://localhost:5055).

---

### Windows

Install [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/). During installation, accept the WSL 2 backend option if prompted. Open Docker Desktop and wait until it shows "Docker Desktop is running" in the system tray before continuing.

Open **PowerShell**:

```powershell
git clone https://github.com/Moose151/project-solace.git
cd project-solace
copy .env.example .env
notepad .env
```

Edit and save `.env`, then:

```powershell
docker compose up -d --build
```

Open [http://localhost:5055](http://localhost:5055).

> **Windows tip:** If `docker compose` isn't found, try `docker-compose` (with a hyphen). Older Docker Desktop versions use the hyphenated form.

> **Windows tip:** If the page doesn't load, check that Docker Desktop is still running (system tray) and that no other service is using port 5055. You can change the port in `.env` by adding `SOLACE_PORT=5056` (or any free port).

---

### Stopping and starting

```bash
docker compose down      # stops and removes the container — data is safe
docker compose up -d     # starts it again
```

**Your data is stored in a Docker named volume (`solace-data`), not inside the container.** Stopping, removing, or rebuilding the container does not delete your bills, users, income sources, or any other data.

The only way to delete the volume (and all data) is to explicitly run:

```bash
docker compose down -v          # ⚠️ deletes the volume and all data
docker volume rm solace-data    # ⚠️ same effect
```

Do not run these commands unless you intend to wipe all data and start fresh.

---

### What happens on container restart

Every time the container starts, it runs a one-time setup check:

- If no database exists yet, it creates one and seeds the initial admin account using the values in your `.env` file.
- If the database already exists, the seed is skipped entirely — your existing users, bills, income sources, and settings are left exactly as they are.
- Any display name or PIN changes you make inside the app are stored in the database and will survive restarts.

In short: **restart safely whenever you need to.** Windows users often need to restart Docker Desktop — this is fine.

---

## Updating

Back up your data before updating (see [Backups](#backups)).

```bash
git pull origin main
docker compose down
docker compose up -d --build
```

Your data volume is untouched. The update only replaces the application code. After starting, confirm the version at **Manage → System Info**.

---

## Configuration

All configuration is done through the `.env` file. Copy `.env.example` to `.env` to get started. The real `.env` is gitignored and must never be committed to version control.

| Variable | Required | Description |
|---|---|---|
| `FLASK_SECRET_KEY` | Yes | Random string used to sign sessions. Generate with `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `SOLACE_ADMIN_USERNAME` | Yes | Internal username for the initial admin account (used for login lookup, not displayed) |
| `SOLACE_ADMIN_PASSWORD` | Yes | PIN for the initial admin account |
| `SOLACE_ADMIN_DISPLAY_NAME` | No | Display name shown on the login screen (default: `Admin`) |
| `DATABASE_URL` | Yes | `sqlite:////app/instance/solace.db` for Docker · `sqlite:///instance/solace.db` for local dev |
| `SOLACE_PORT` | No | Host port to expose (default: `5055`) |
| `FLASK_DEBUG` | No | `true` for local dev · `false` (default) for production |

> These values are only used to seed the initial account. Once the account exists in the database, changes made inside the app take effect immediately and are not overwritten by `.env` on restart.

**Example `.env` for Docker:**

```env
FLASK_SECRET_KEY=replace-with-a-long-random-string
SOLACE_ADMIN_USERNAME=admin
SOLACE_ADMIN_PASSWORD=your-strong-pin
SOLACE_ADMIN_DISPLAY_NAME=Household
DATABASE_URL=sqlite:////app/instance/solace.db
FLASK_DEBUG=false
```

**Example `.env` for local development:**

```env
FLASK_SECRET_KEY=local-dev-secret
SOLACE_ADMIN_USERNAME=admin
SOLACE_ADMIN_PASSWORD=1234
DATABASE_URL=sqlite:///instance/solace.db
FLASK_DEBUG=true
```

---

## User accounts

### The initial admin account

When the container starts for the first time, one admin account is created using the credentials in your `.env` file. This is the only account initially — you can add more users from **Manage → Users** once you are logged in.

### Changing your display name or PIN

Log in and go to the user icon (top right) → **My Account**. You can change your display name and PIN there at any time. These changes are saved to the database immediately.

### Adding more users

Go to **Manage → Users** → **Add user**. Each user gets their own display name, emoji avatar, and PIN. All users see and edit the same household data — there is no per-user data separation.

### If the database is reset

If you ever need to start fresh (by deleting the volume), the admin account will be re-seeded from `.env`. Make sure `SOLACE_ADMIN_PASSWORD` and `SOLACE_ADMIN_DISPLAY_NAME` are set to what you want before doing this.

---

## Backups

Use **Manage → Backup & Restore** in the app before applying updates.

- The **SQLite database ZIP** is the full, restore-capable backup.
- XLSX / CSV exports are useful for review but cannot restore the database.

To back up the database directly from the Docker volume:

```bash
docker run --rm -v solace-data:/data -v $(pwd):/backup alpine \
  tar -czf /backup/solace-backup-$(date +%F).tar.gz -C /data .
```

On Windows PowerShell:

```powershell
docker run --rm -v solace-data:/data -v ${PWD}:/backup alpine `
  tar -czf /backup/solace-backup.tar.gz -C /data .
```

---

## Local development (no Docker)

### Linux / macOS

```bash
git clone https://github.com/Moose151/project-solace.git
cd project-solace
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
# edit .env for local dev
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
python run.py
```

Open [http://localhost:5000](http://localhost:5000).

To deactivate the virtual environment when done:

```bat
.venv\Scripts\deactivate
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
- Container runs as a non-root user (uid 1000)

One worker is used intentionally — multiple workers can cause SQLite contention during startup.

---

## License

Project Solace is personal/hobbyist software shared publicly. No formal license is currently attached. If you intend to fork or redistribute it, please open an issue to discuss.
