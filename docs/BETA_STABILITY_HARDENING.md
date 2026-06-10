# Project Solace Beta 0.24.1 Stability Hardening

Project Solace is still considered beta software. The older v1-v24 labels were rapid internal build numbers used while the app was being shaped. The app now reports beta-style versions, starting with `0.24.1-beta`.

This build intentionally avoids major new user-facing features. It focuses on reliability, safety, and pre-stress-test hardening.

## Included hardening work

- Development debug mode is now controlled by `FLASK_DEBUG` instead of being hardcoded on.
- The Docker image now runs the application as a non-root user.
- Missing `FLASK_SECRET_KEY` and `SOLACE_ADMIN_PASSWORD` now raise visible startup warnings before using development fallbacks.
- Default new installs use the current year instead of hardcoded 2026 settings.
- Date fields now validate at form level before route logic runs.
- Money inputs have upper bounds to catch accidental oversized entries.
- Webhook URLs receive basic URL validation.
- Weekly and fortnightly bill-date generation now fast-forwards to the relevant year instead of stepping from old start dates one interval at a time.
- Unknown bill frequencies now fail loudly instead of silently producing zero annual cost.
- Several delete/edit/action routes now use graceful 404 handling for missing records.
- Restore/import uploads now have explicit size checks.
- Bill import preview is stored in the instance folder rather than the client-side Flask session cookie.
- Temporary XLSX/ZIP export files are cleaned up after the response.
- Common query columns now have indexes for existing and new SQLite databases.
- A small pytest suite was added for core calculation logic and smoke testing.
- Dependabot was added for Python dependency update alerts.

## Server deployment note

The container now runs as UID 1000 (`appuser`). Before deploying this build on an existing server, make sure the persistent instance folder can be written by UID 1000:

```bash
cd /opt/docker/project-solace/app
sudo chown -R 1000:1000 instance
```

Then rebuild normally:

```bash
docker compose down
docker compose build --no-cache
docker compose up -d
```

## Recommended freeze

After this build, avoid new features until Project Solace has been used through at least one full pay cycle. Focus only on bug fixes, backup/restore testing, and small wording/layout fixes.
