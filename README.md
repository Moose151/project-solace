# Project Solace

Self-hosted household set-aside planner for recurring bills, planned purchases, income sources, and bucket-based pay allocation.

## v10.1 notes

This build fixes the v10 issues reported during testing:

- Dashboard setup panel can now be dismissed. There is a POST button and a fallback dismiss link.
- Calendar is now a top-level navigation item and also available from the dashboard.
- Monthly view supports Calendar and List modes and shows both bills and income.
- Buckets now explicitly use either Percentage of income or Fixed household amount.
- Fixed household buckets are split between people by income share, not 50/50.
- Only one bucket can use the remainder cap.

## Local run

```bash
cd ~/Documents/project-solace
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

Open http://localhost:5000

## Docker run

```bash
cp .env.example .env
docker compose up -d --build
```

Open http://localhost:5055
