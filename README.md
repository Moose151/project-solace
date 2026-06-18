# Project Solace

Current build: **0.27.0-beta — Avatar Login**

Project Solace is a self-hosted household set-aside planner for recurring bills, planned purchases, income sources, and bucket-based payday transfers.

It is intentionally not a full transaction-tracking budget app. Its main job is to answer: **how much should each person transfer into each bucket this pay cycle?**

---

## Versioning

Project Solace is in beta. Earlier ZIP/build labels such as v1–v24 were rapid internal build numbers, not production release versions. The app uses beta-style versioning:

```text
0.x.y-beta
```

The current build is **0.27.0-beta**.

---

## Feature set

### Authentication

- Meridian-style avatar/PIN login — tap your card, enter your PIN
- User management at **Manage → Users**
- Per-user display name and avatar emoji

### Planning

- Recurring bills (weekly, fortnightly, monthly, quarterly, six-monthly, yearly)
- Income sources per person (weekly or fortnightly), including shared household income
- Shared income allocation modes: standard, lump sum to a bucket, or custom per-bucket split
- Bucket allocations by percentage or fixed amount, with remainder/cap and rounding
- Per-person contribution breakdowns
- Fortnightly and weekly pay-cycle support
- Current and next pay cycle preview
- Payday checklist with transfer items, hide/restore, and income confirmation
- Cycle closeout with actual income field
- Cycle history (Planning → Cycle History)
- Annual / financial year summary (Planning → Annual Summary)
- Per-category budget envelopes with over/under indicator

### Dashboard

- Modular, configurable dashboard layout (Manage → Dashboard Layout)
- Widgets: cycle summary, bills due, bucket summaries, per-person contributions, planned purchases, payday checklist preview, overdue bills, bills bucket health, account balance snapshot, recurring totals, savings goals
- AJAX paid/skip on bill widgets — no page reload, toast feedback, running total update
- Savings goals widget with progress bars, per-fortnight set-aside, weeks to target, and mark-purchased shortcut

### Calendar

- Month grid and list views
- Mobile agenda view grouped by Today / This Week / Coming Up / Past
- Overdue unpaid bills shown above the calendar in a red card
- Colour legend (bill / income / paid / skipped) on desktop
- Quick-add `+` link on desktop day cells, pre-fills the bill form date
- Bill events link to the bill detail page

### Other

- Planned purchases: shared (household) and individual (per person)
- Privacy filter — blurs money values on screen, stored in browser local storage
- Bill search / live client-side filter on the bills page
- Bill detail page with audit log of amount changes
- Back button navigation on detail/edit pages
- Health check page (Manage → Health Check)
- System Info / Diagnostics page (Manage → System Info)
- Backup and restore (Manage → Backup & Restore)
- Import preview with confirm/cancel flow
- XLSX and ZIP export
- Audit log
- Dark mode
- ntfy / Gotify push notification test send
- Docker deployment
- Dependabot for dependency alerts

---

## Local development — Linux / macOS

Install prerequisites (Ubuntu/Debian):

```bash
sudo apt update
sudo apt install git python3 python3-pip python3-venv
```

Clone and set up:

```bash
mkdir -p ~/Documents
cd ~/Documents
git clone https://github.com/Moose151/project-solace.git
cd project-solace
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Configure environment:

```bash
cp .env.example .env
nano .env
```

Minimal `.env` for local development:

```env
FLASK_SECRET_KEY=local-dev-secret
SOLACE_ADMIN_USERNAME=admin
SOLACE_ADMIN_PASSWORD=admin
DATABASE_URL=sqlite:///instance/solace.db
FLASK_DEBUG=true
```

Run:

```bash
python run.py
```

Open:

```text
http://localhost:5000
```

---

## Local development — Windows

Install [Python 3](https://www.python.org/downloads/windows/) (tick **Add Python to PATH** during install) and [Git for Windows](https://git-scm.com/download/win).

Open **Command Prompt** or **PowerShell**:

```bat
git clone https://github.com/Moose151/project-solace.git
cd project-solace
python -m venv .venv
.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

Configure environment:

```bat
copy .env.example .env
notepad .env
```

Minimal `.env` for local development on Windows:

```env
FLASK_SECRET_KEY=local-dev-secret
SOLACE_ADMIN_USERNAME=admin
SOLACE_ADMIN_PASSWORD=admin
DATABASE_URL=sqlite:///instance/solace.db
FLASK_DEBUG=true
```

Run:

```bat
python run.py
```

Open:

```text
http://localhost:5000
```

To deactivate the virtual environment when done:

```bat
.venv\Scripts\deactivate
```

---

## Docker — Linux (standard)

```bash
cp .env.example .env
nano .env
docker compose up -d --build
```

Open:

```text
http://localhost:5055
```

---

## Docker — Linux with SELinux (Fedora / RHEL)

The Docker Compose volume mount uses `:Z` for SELinux relabelling:

```yaml
./instance:/app/instance:Z
```

This is already present in the provided `docker-compose.yml`. Do not remove it on SELinux hosts.

The container runs as a non-root user (`UID 1000`). If the `instance/` folder was previously owned by root, fix it before starting:

```bash
sudo chown -R 1000:1000 instance
```

Then deploy:

```bash
cp .env.example .env
nano .env
docker compose up -d --build
docker compose ps
docker compose logs --tail=50
```

---

## Docker — Windows

Install [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/) and ensure it is running.

Open **PowerShell** in the project folder:

```powershell
copy .env.example .env
notepad .env
docker compose up -d --build
```

Open:

```text
http://localhost:5055
```

To stop:

```powershell
docker compose down
```

> **Note:** On Windows, Docker Desktop uses WSL 2 by default. The `:Z` SELinux label in the volume mount is silently ignored on Windows — this is safe.

---

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `FLASK_SECRET_KEY` | Yes | Random secret for session signing. Generate with `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `SOLACE_ADMIN_USERNAME` | Yes | Admin account username |
| `SOLACE_ADMIN_PASSWORD` | Yes | Admin account password / PIN |
| `DATABASE_URL` | Yes | SQLite path. Use `sqlite:////app/instance/solace.db` in Docker, `sqlite:///instance/solace.db` for local dev |
| `FLASK_DEBUG` | No | Set `false` on the server. Default is `false` |

The real `.env` must never be committed. Only `.env.example` (with placeholders) is tracked by Git.

---

## Server update workflow

After pushing a new version to GitHub, update the server:

```bash
cd /opt/docker/project-solace/app

# Back up the database first
mkdir -p /opt/docker/backups/project-solace
tar -czf /opt/docker/backups/project-solace/project-solace-before-update-$(date +%F-%H%M).tar.gz instance

git pull origin main
sudo chown -R 1000:1000 instance
docker compose down
docker compose build --no-cache
docker compose up -d
docker compose ps
docker compose logs --tail=80
```

Confirm the running version at `/system-info`.

---

## Backups

Use **Manage → Backup & Restore** before applying updates.

- The **SQLite database ZIP** is the restore-capable backup.
- CSV/XLSX exports are useful for review but cannot be used to restore the database.

---

## Server stability defaults

The Docker build is configured for small household self-hosting with SQLite:

- Gunicorn: `1` worker, `4` threads, `60` second timeout.
- SQLite WAL mode and a `30` second busy timeout are enabled at app startup.
- Startup database setup is serialised with an instance-folder lock file.
- Docker Compose mounts `./instance:/app/instance:Z` for Fedora/SELinux compatibility.

One worker was chosen deliberately — two workers caused an SQLite race condition during admin seeding on first boot.
