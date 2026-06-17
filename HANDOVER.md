# Project Solace — AI / Developer Handover

## Purpose of this file

This file is intended to let another AI assistant or developer continue work on Project Solace without needing the full prior conversation. It captures the project purpose, technical stack, workflow, deployment details, current features, decisions already made, known issues, and future backlog.

Project Solace is still considered **beta software**. The current project line uses beta-style versioning such as `0.24.1-beta` and `0.24.2-beta`. Older labels such as v1–v24 were internal rapid-build labels used during development and should not be treated as stable production release numbers.

---

## 1. Project overview

Project Solace is a self-hosted household finance planning app.

Its main purpose is to help a household answer:

> How much should each person transfer, save, or keep aside each pay cycle so recurring bills, shared buckets, savings, and planned purchases are covered?

It is built for a household where two people have separate incomes, are paid fortnightly, and need a simple planning tool that works well on mobile.

Project Solace is **not** intended to be a full transaction tracker or complete accounting system. It is deliberately not trying to replace apps like Actual Budget, YNAB, or a bank ledger. It should not become a tool for importing bank transactions, reconciling accounts, tracking every spend, or categorising every card transaction.

The intended scope is:

- Recurring bills
- Income sources
- Pay-cycle planning
- Bucket transfers
- Shared and individual planned purchases
- Calendar/list visibility of upcoming bills and income
- Payday checklist
- Cycle closeout
- Light backup/restore/export support
- Mobile-friendly household use

The design goal is a reliable, practical, low-friction household planning app.

---

## 2. User and household context

The app is primarily for Nick and Em.

The household has two income sources, with both people paid fortnightly in the same broad pay cycle but on different days. Example values used during testing included:

- Em income: `$2558.00`, fortnightly
- Nick income: `$3090.00`, fortnightly
- Combined household income: `$5648.00`

The app should support multiple income sources and assign each to a person.

Important concept: the income date stored for each income source should be treated as a **known pay date anchor**, not a manually updated “next pay date”.

The user specifically wanted the old wording changed from:

- `Next pay date`

to:

- `Known pay date`

because the date can be in the past and is used as a recurrence anchor.

The app calculates current and future pay cycles from active income sources. `Settings.first_payday` should only be used as a fallback if no active income source exists.

---

## 3. Core budget workflow

The normal household workflow is:

1. Add income sources for each person.
2. Add recurring bills.
3. Add buckets such as Bills, Savings, Shared Spending, and Individual Spending.
4. Use Pay Cycle and Pay Split pages to work out what each person should transfer.
5. Use Payday Checklist on payday to complete transfer/checklist items.
6. Use Calendar/List views to see upcoming bills and paydays.
7. Mark bill occurrences as paid or skipped.
8. Use Planned Purchases for upcoming shared or individual goals.
9. Optionally use Cycle Closeout at the end of a cycle.

Example buckets seen during testing:

- Bills: `$1980.00`
- Savings: `$2300.00`
- Shared spending: `$850.00`
- Individual spending: `$518.00`

Example per-person split seen during testing:

Em:

- Income: `$2558.00`
- Bills/planned buckets: `$900.00`
- Total buckets: `$2540.00`
- Remaining: `$18.00`

Nick:

- Income: `$3090.00`
- Bills/planned buckets: `$1080.00`
- Total buckets: `$3050.00`
- Remaining: `$40.00`

The app should preserve the distinction between:

- Shared household set-aside
- Each person’s individual spending
- Shared planned purchases
- Individual planned purchases

---

## 4. Pay-cycle rules

Active income sources are the primary source of truth for pay-cycle rhythm.

The app supports current and next cycle views.

Known pay dates are recurrence anchors. They can be in the past and should not need fortnightly manual updates.

Pay-cycle example from testing:

- Current cycle: `03 Jun 2026 – 16 Jun 2026`
- Next payday: `17 Jun 2026`

Important bug already fixed:

The app previously showed bills due on `17 Jun 2026` under “due before next pay” for the `03 Jun – 16 Jun` cycle. This was wrong because those bills belonged to the next cycle. The fix was to include bills up to `cycle_end`, not `next_payday`.

There is a setting for whether bills due on payday belong to the new cycle or previous cycle. Current preferred behaviour is:

- Bills due on payday belong to the **new pay cycle**

Do not remove this setting.

---

## 5. Technical stack

Project Solace is a Flask application.

Main technologies:

- Python
- Flask
- Flask-SQLAlchemy
- Flask-Login
- Flask-WTF / WTForms
- SQLite
- Gunicorn
- Docker / Docker Compose
- Jinja templates
- CSS in `app/static/css/site.css`
- pytest
- Dependabot for Python dependency update alerts

Repository:

```text
https://github.com/Moose151/project-solace
```

Typical local path:

```text
~/Documents/project-solace
```

Main app entry point:

```text
run.py
```

Important app files:

```text
app/__init__.py
app/models.py
app/forms.py
app/routes.py
app/budget_engine.py
app/version.py
app/static/css/site.css
app/templates/
tests/
docs/
```

The project uses an app factory pattern via `create_app()`.

---

## 6. Deployment and hosting

Project Solace is deployed on a Fedora Server using Docker Compose.

Server app path:

```text
/opt/docker/project-solace/app
```

Server URL:

```text
http://192.168.1.125:5055
```

Container name:

```text
project-solace
```

Persistent data path:

```text
/opt/docker/project-solace/app/instance
```

SQLite database is stored in the `instance/` directory. The database must not be committed to Git.

The server uses Fedora/SELinux, so the Docker volume mount needs SELinux relabelling:

```text
./instance:/app/instance:Z
```

This `:Z` mount option is important. Do not remove it unless you understand the SELinux implications.

Gunicorn should run with one worker and four threads:

```text
gunicorn -w 1 --threads 4 --timeout 60 -b 0.0.0.0:5000 run:app
```

This setup was chosen deliberately because earlier two-worker startup caused an SQLite/admin seed race:

```text
UNIQUE constraint failed: user.username
```

The app now includes race-safe startup seeding, SQLite WAL mode, `busy_timeout`, and related stability improvements.

The Docker container was hardened to run as a non-root user. When deploying builds that use the non-root user, the server `instance` folder may need:

```bash
sudo chown -R 1000:1000 instance
```

---

## 7. Environment variables

The app uses `.env`.

The real `.env` must remain untracked and should never be committed.

Example `.env` for Docker/server:

```env
FLASK_SECRET_KEY=long-random-secret
SOLACE_ADMIN_USERNAME=admin
SOLACE_ADMIN_PASSWORD=strong-password
DATABASE_URL=sqlite:////app/instance/solace.db
FLASK_DEBUG=false
```

Example `.env` for local development:

```env
FLASK_SECRET_KEY=local-dev-secret
SOLACE_ADMIN_USERNAME=admin
SOLACE_ADMIN_PASSWORD=admin
DATABASE_URL=sqlite:///instance/solace.db
FLASK_DEBUG=true
```

Generate a strong local or server secret:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

The repository should ignore:

```text
.env
.env.*
instance/
*.db
*.sqlite
*.sqlite3
backups/
exports/
uploads/
*.zip
.venv/
```

`.env.example` is allowed to be tracked because it contains placeholders only.

---

## 8. Common local development workflow

On Ubuntu:

```bash
sudo apt update
sudo apt install git python3 python3-pip python3-venv
```

Clone:

```bash
mkdir -p ~/Documents
cd ~/Documents
git clone https://github.com/Moose151/project-solace.git
cd project-solace
```

Set up Python environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Create `.env` if missing:

```bash
cp .env.example .env
nano .env
```

Run locally:

```bash
python run.py
```

Open:

```text
http://localhost:5000
```

Check version/system info:

```text
http://localhost:5000/system-info
```

---

## 9. Common Git workflow

The user often works across multiple laptops and the server. Be careful with Git.

Set Git identity if needed:

```bash
git config --global user.name "Nick Lister"
git config --global user.email "nicklister15@gmail.com"
```

Normal local workflow:

```bash
cd ~/Documents/project-solace
git status
git add .
git commit -m "Describe the change"
git pull --rebase origin main
git push origin main
```

If `git pull --rebase` produces conflicts, do not push until conflicts are resolved.

Inspect state:

```bash
git status
git log --oneline --decorate -8
```

Continue rebase after resolving conflicts:

```bash
git add <resolved-files>
git rebase --continue
```

Abort rebase if necessary:

```bash
git rebase --abort
```

The user previously had issues where changes were staged but not committed, or committed locally but not pushed. Always verify:

```bash
git log --oneline --decorate -5
git status
```

---

## 10. Server update workflow

After successfully pushing to GitHub:

```bash
cd /opt/docker/project-solace/app
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

Then check:

```text
http://192.168.1.125:5055/system-info
```

Confirm the running version matches the expected beta version.

---

## 11. Current feature set

### Authentication

- Admin login exists.
- Admin credentials are seeded from environment variables.
- Missing `FLASK_SECRET_KEY` and `SOLACE_ADMIN_PASSWORD` should warn loudly after stability hardening.
- Do not rely on `admin/admin` on the live server.

### Dashboard

Dashboard shows household summary information and configurable widgets.

Dashboard may include:

- Current cycle summary
- Bills due/unpaid this cycle
- Bucket summaries
- Individual contribution summaries
- Quick links
- Planned purchase summaries
- Calendar/overview widgets

Dashboard layout is modular and configurable via:

```text
Manage → Dashboard Layout
```

### Recurring bills

Bills support:

- Name
- Amount
- Frequency
- First due date
- Optional stop-after date
- Category
- Account paid from
- Active flag
- Autopay flag
- Include in set-aside flag
- Notes
- Occurrence handling

The bill form must use:

```text
First due date
```

Do not reintroduce separate confusing user-facing fields:

```text
Due day
Due month
Start date
```

Frequencies include:

- Weekly
- Fortnightly
- Monthly
- Quarterly
- Six-monthly
- Yearly

Bill occurrences support statuses such as:

- Upcoming
- Paid
- Skipped

Bill detail page exists and should be preserved.

### Income sources

Income sources support:

- Person
- Source name
- Amount
- Frequency
- Known pay date
- Active flag
- Notes

The correct label is:

```text
Known pay date
```

Do not call this “Next pay date” in the UI.

### Pay Cycle

Pay Cycle supports:

- Current cycle
- Next cycle
- Closeout navigation

This was added because the user specifically wanted to preview the next cycle’s bills and transfers.

### Payday Checklist

Payday Checklist supports:

- Current cycle
- Next cycle
- Transfer/checklist items
- Hiding automatic transfers
- Restoring hidden transfers

The page previously had rendering and recursion bugs. Be careful changing `get_cycle_window()` and the checklist logic.

### Cycle Closeout

Cycle Closeout exists under Planning.

It shows:

- Bills expected this cycle
- Paid bills
- Skipped bills
- Unpaid bills
- Bucket transfer/checklist completion
- Close cycle button
- Notes

It should remain lightweight and not become a full transaction ledger.

### Buckets

Buckets support:

- Percentage amount
- Fixed amount
- Remainder/cap-to-remaining behaviour
- Per-person and combined contribution breakdowns

Only one bucket may use the remainder/cap behaviour.

This is a locked-in user requirement.

### Planned Purchases

Planned purchases support:

- Shared planned purchases
- Individual planned purchases

Important fields added:

```text
purchase_scope
owner_name
```

Shared purchases:

- Household-level
- Both incomes contribute toward them
- Count toward shared planned-purchase set-aside

Individual purchases:

- Assigned to one person
- Come from that person’s individual spending
- Should not increase household shared planned-purchase bucket requirements

Planned Purchases page separates:

- Shared planned purchases
- Individual planned purchases by person
- All planned purchases

### Calendar

Calendar supports:

- Month view
- List view
- Mobile agenda-style view
- Current day highlighting
- Previous / this month / next controls
- Bill and income events
- Paid/skipped/upcoming visual distinctions
- Bill events linking to bill detail

0.24.2-beta added:

- Date pickers
- Mobile agenda-style view
- Better mobile usability

### Privacy mode

A Privacy button exists in the navbar.

It blurs money values on screen, similar to Actual Budget’s privacy mode.

Behaviour:

- Stored in browser local storage
- Persists per browser
- Should blur visible money values across the page

### Backup / restore / import / export

Built:

- Backup/restore page
- Import preview
- Confirm/cancel import flow
- XLSX/ZIP exports
- Upload size limits
- Temp file cleanup
- Import preview stored in instance/temp storage rather than Flask cookie session

### Health Check

Health Check page exists under Manage.

Checks include:

- Active income sources
- Active bills
- Uncategorized bills
- Multiple remainder buckets
- Percentage bucket totals
- Overdue unpaid bills
- Payday bill handling setting
- Database file check
- App version check

### System Info

System Info exists under Manage.

It should show:

- App version
- Release name
- Git commit if available
- Python version
- Debug mode
- Database URI/path
- Database exists
- Database size
- Current pay cycle
- Next payday
- Active bills
- Active income sources
- Active buckets
- Active planned purchases
- Unpaid bill occurrences
- Overdue unpaid occurrences

This is important for troubleshooting server update issues.

---

## 12. Design and UX decisions

Design language:

```text
HomeStack UI
```

This design direction should eventually be shared with Project Meridian and a future home server dashboard.

Preferred UI feel:

- Warm
- Soft
- Household-friendly
- Minimal but not empty
- Clean and calm
- Not childish
- Not corporate
- Not overly technical
- Mobile-friendly

Palette:

```text
Light background:        #f6f1e8
Light surface:           #fffaf2
Raised surface:          #ffffff
Soft surface:            #f2eadf
Border:                  #ded4c5
Main text:               #252525
Muted text:              #6f6a61
Primary accent:          #3f6f8f
Primary hover:           #315a75
Success:                 #5f8f6b
Warning:                 #c98a3d
Danger:                  #b85c50

Dark background:         #171615
Dark surface:            #22201d
Dark raised surface:     #2b2824
Dark border:             #403a33
Dark text:               #f2eee7
Dark muted text:         #b8afa3
```

Mobile UX rules:

- Mobile is a priority.
- Touch targets should be large.
- Tables should become cards or agenda views where needed.
- Date fields should provide calendar pickers.
- Money fields should request decimal numeric keypad.
- Whole-number fields should request numeric keypad.
- Mobile hamburger menu must not be blocked by fixed bottom nav.
- Bottom nav can remain, but open menu content needs enough bottom spacing/scroll clearance.

---

## 13. Version/build history

The app was developed rapidly through internal labels v1–v24 and is now considered beta.

Current beta line:

```text
0.24.x-beta
```

Important milestones:

- v1: MVP with bills, planned purchases, dashboard, settings, Docker
- v2: Australian date parsing
- v3: CSRF display fix
- v4: Usability update
- v5: Import/export/backup, balances, dark mode, Docker/Gunicorn
- v6: Income sources, buckets, pay split
- v7: Remainder/cap bucket
- v8: Per-person buckets
- v9: GUI and bucket cleanup
- v10/v10.1: Dashboard/calendar/bucket fixes
- v11: Modular dashboard and dark mode
- v12: Dark mode polish
- v13: Payday workflow, backup/restore, audit log
- v14: Checklist/tooltips
- v15: Server stability
- v16: Bill sorting and category overview
- v17: Navigation and dashboard polish
- v18: HomeStack UI warm theme
- v19: Mobile-first polish
- v20: Bill entry and calendar refine
- v20.1: Calendar `month_name` fix
- v21: Income cycle cleanup
- v21.1: Pay-cycle due range fix
- v22: Pay cycle preview, closeout, health check
- v22.1: Payday rendering fix
- v23: Privacy filter and planned purchase scope
- v24: System Info and diagnostics polish
- 0.24.1-beta: Stability Hardening
- 0.24.2-beta: Mobile Usability Patch

Latest created build:

```text
Project Solace 0.24.2-beta — Mobile Usability Patch
```

---

## 14. Features added recently

Recent completed additions include:

- Beta versioning instead of “v25”
- System Info page
- Health Check improvements
- Privacy money blur
- Shared vs individual planned purchases
- Current/next cycle preview
- Cycle Closeout
- Bill detail page
- Calendar event links to bill detail
- Mobile bottom nav
- Mobile hamburger overlap fix
- Mobile agenda-style calendar
- Date picker fields
- Mobile numeric/decimal keypad support
- Non-root Docker user
- Env-driven debug mode
- Date validation
- Money upper bounds
- Upload size limits
- Faster weekly/fortnightly bill generation
- pytest smoke/calculation tests
- Dependabot config

---

## 15. Features yet to implement

These are backlog items. Do not add major features until the current beta is stress tested.

### Calendar improvements

Future calendar work:

- Better mobile agenda layout
- Today card
- This week section
- Upcoming bills section
- Upcoming income section
- Expandable day cards
- Calendar legend
- Paydays highlighted separately from ordinary income
- Bills due today highlighted
- Overdue unpaid bills surfaced above the calendar

### Calendar action sheet

On mobile, tapping a bill event should eventually open an action sheet with:

- View bill
- Mark paid
- Skip this occurrence
- Edit bill

For income events:

- View income source
- View pay cycle
- View payday checklist

### More tests

Expand tests for:

- Weekly/fortnightly bill generation
- Monthly short-month behaviour
- Bills due on payday setting
- Multiple income-source pay cycle handling
- Shared planned purchases
- Individual planned purchases
- Bucket remainder/cap behaviour
- Backup/restore safety
- Import preview safety
- Health Check outputs

### Release workflow

Create GitHub release tags for stable beta snapshots.

Suggested tags:

```text
beta-0.24.1
beta-0.24.2
```

### Migration system

Eventually replace or supplement lightweight migrations with Flask-Migrate/Alembic.

Do this before many more schema changes.

### Date and money schema migration

Long-term:

- Move date strings to `db.Date` / `db.DateTime`
- Move money floats to `db.Numeric(10, 2)` or Decimal-backed handling

Do not do this casually. It requires a migration plan and backup testing.

### Dashboard refactor

Eventually split dashboard route into helper functions:

- `get_dashboard_bill_data()`
- `get_dashboard_income_data()`
- `get_dashboard_bucket_data()`
- `get_dashboard_checklist_data()`

This is maintainability work, not urgent unless dashboard bugs/performance issues appear.

### Notifications

Notification settings scaffold exists, but notifications are not a major active workflow.

Possible future choices:

- In-app notifications
- ntfy/Gotify
- Email/SMTP

Preferred direction: keep simple and self-hosting-friendly.

### HomeStack UI extraction

Eventually move reusable UI styles into a shared HomeStack UI file or pattern that can be used by:

- Project Solace
- Project Meridian
- Home server dashboard

---

## 16. Known issues and technical debt

### Date storage as strings

Many date fields are currently stored as `String(10)`.

This works if ISO format is consistent, but `db.Date` would be cleaner long term.

Do not change during stress testing unless necessary.

### Money storage as floats

Money fields are currently floats.

This is acceptable for household planning with rounding helpers but not ideal.

Long-term use Decimal/Numeric.

### Lightweight migrations getting large

`apply_lightweight_migrations()` has grown and should eventually be split into:

- Schema migrations
- Data migrations
- Seeding/default data

### Dashboard route complexity

The dashboard route does a lot of work. Leave it for now unless it becomes unstable.

### Notification token storage

Notification webhook/token fields are stored in plaintext. Acceptable for trusted LAN use for now but document before expanding notifications.

### Git workflow complexity

The user works across multiple laptops and server copies. Always confirm Git status before giving commands that overwrite or rebase.

---

## 17. Security notes

Do not commit:

- `.env`
- `instance/`
- `solace.db`
- backups
- exports
- real secrets
- real passwords

The public repo has been checked previously. It should only expose `.env.example` with placeholder values.

If a secret is pasted into chat or committed accidentally:

1. Rotate it.
2. Verify it is not tracked.
3. Check Git history if it was committed.
4. Consider history rewrite only if an actual live secret was pushed.

Server `.env` should have a strong:

```env
FLASK_SECRET_KEY
SOLACE_ADMIN_PASSWORD
```

`FLASK_DEBUG` should be false on the server.

---

## 18. Project Meridian relationship

Project Meridian is a separate household gamified task/reward Flask app.

Repository:

```text
https://github.com/Moose151/project-meridian
```

The user wants Meridian to eventually share Solace’s HomeStack UI design.

Important Meridian-specific rule:

Do not hardcode visible “points” text in Meridian. Use the dynamic household settings label:

```text
household_settings.points_label
```

Meridian has:

- Admin/user roles
- Avatar login
- 4-digit PIN
- Tasks
- Hot Tasks already implemented
- Rewards
- Approvals
- Points history
- Household points label
- Categories
- Potential Raspberry Pi touchscreen kiosk/hub use

Do not confuse Solace and Meridian folders:

```text
~/Documents/project-solace
~/Documents/project-meridian
```

---

## 19. Assistant/user working preferences

The user prefers:

- Direct practical help
- Exact commands
- Step-by-step guidance
- Code examples with comments
- Warnings when something is risky
- No over-engineering
- Stability over novelty
- Mobile usability
- Clear version/deployment checks

When helping with this project:

- Ask for `git status` before resolving Git problems.
- Avoid telling the user to overwrite files unless a backup exists.
- Do not propose full transaction tracking unless explicitly requested.
- Do not relitigate already-decided scope.
- Treat small mobile/UI fixes as acceptable during beta.
- Treat new financial logic/schema changes as risky and requiring tests/backups.
- Always preserve `.env`, `.venv`, `.git`, and `instance/` when replacing files from ZIPs.

---

## 20. Current recommended next steps

Immediate next phase:

1. Commit and deploy `0.24.2-beta` if not already done.
2. Verify `/system-info` on the server.
3. Create a known-good backup.
4. Freeze major features.
5. Stress test with real household data.
6. Log bugs/QoL issues.
7. Only patch stability/mobile usability bugs during beta.

Suggested stress-test checklist:

```text
Dashboard loads
System Info loads
Health Check loads
Privacy toggle works
Bills add/edit/delete works
Bill occurrence paid/skipped works
Calendar desktop view works
Calendar mobile agenda works
Current day highlight works
Income source known pay date works
Pay Cycle current works
Pay Cycle next works
Payday Checklist current works
Payday Checklist next works
Pay Split works
Shared planned purchase works
Individual planned purchase works
Backup download works
Restore/import size limits work
Mobile nav menu scrolls above bottom nav
Money fields open numeric keypad on mobile
Date fields open date picker on mobile
```

Do not begin large refactors until after this stress testing period.
