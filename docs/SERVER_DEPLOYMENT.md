# Project Solace server deployment

This guide assumes you have a Linux server with Docker and Docker Compose installed.

## 1. Create a GitHub repository

On GitHub, create a new empty repository named `project-solace`.

Do not add a README, licence, or `.gitignore` on GitHub if you are pushing this package as the first commit.

## 2. Push from your development machine

From inside the `project-solace` folder:

```bash
git init
git add .
git commit -m "Initial Project Solace app"
git branch -M main
git remote add origin git@github.com:YOUR_USERNAME/project-solace.git
git push -u origin main
```

If you use HTTPS instead of SSH:

```bash
git remote add origin https://github.com/YOUR_USERNAME/project-solace.git
```

## 3. Clone on your server

SSH into your server, then run:

```bash
cd /opt
sudo git clone git@github.com:YOUR_USERNAME/project-solace.git
sudo chown -R $USER:$USER project-solace
cd project-solace
```

Using your home folder is also fine:

```bash
cd ~
git clone git@github.com:YOUR_USERNAME/project-solace.git
cd project-solace
```

## 4. Create your server environment file

```bash
cp .env.example .env
nano .env
```

Change at least these values:

```env
FLASK_SECRET_KEY=use-a-long-random-secret
SOLACE_ADMIN_USERNAME=admin
SOLACE_ADMIN_PASSWORD=use-a-strong-password
SOLACE_PORT=5055
```

Generate a strong Flask secret with:

```bash
python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(48))
PY
```

## 5. Start Project Solace

```bash
mkdir -p instance
sudo chown -R 1000:1000 instance
docker compose up -d --build
```

If the container cannot open the SQLite database after a hardening update, check instance-folder ownership:

```bash
cd /opt/docker/project-solace/app
sudo chown -R 1000:1000 instance
docker compose up -d --build
```

The container runs as non-root UID 1000. The `chown` command makes sure the SQLite instance folder is writable by the app user inside the container.

Then open:

```text
http://SERVER-IP:5055
```

## 6. Updating later

From the server project folder:

```bash
./scripts/deploy.sh
```

That script backs up `instance/solace.db`, pulls the latest GitHub changes, rebuilds the container, and restarts it.

## 7. Nginx Proxy Manager

Create a Proxy Host in Nginx Proxy Manager:

```text
Domain Names: solace.yourdomain.com
Scheme: http
Forward Hostname/IP: SERVER-IP or project-solace host IP
Forward Port: 5055
Websockets Support: optional/off
Block Common Exploits: on
```

Request an SSL certificate through Nginx Proxy Manager if exposing it beyond your LAN.

## 8. Data persistence

The app database is stored outside the container at:

```text
instance/solace.db
```

This folder is intentionally ignored by Git. Do not commit it to GitHub.

## 9. Manual database backup

```bash
./scripts/backup-db.sh
```

## Fedora Server stability notes

For the Fedora Server deployment, keep the persistent SQLite database in the `instance` folder and mount it with the SELinux relabel flag:

```yaml
volumes:
  - ./instance:/app/instance:Z
```

The production container uses Gunicorn with one worker and four threads:

```dockerfile
CMD ["gunicorn", "-w", "1", "--threads", "4", "--timeout", "60", "-b", "0.0.0.0:5000", "run:app"]
```

This is the recommended default for the current SQLite-backed household deployment. It allows multiple browser sessions to use the app at the same time while avoiding the extra SQLite write contention that can come from multiple worker processes.

Project Solace also enables SQLite WAL mode and a 30-second busy timeout at startup. Startup database setup is protected by a lock file in the instance folder so Gunicorn workers cannot race while seeding default data.

Useful server commands:

```bash
cd /opt/docker/project-solace/app
docker compose ps
docker compose logs -f
docker compose restart
docker compose down
docker compose up -d --build
```

Manual backup before updates:

```bash
cd /opt/docker/project-solace/app
mkdir -p /opt/docker/backups/project-solace
tar -czf /opt/docker/backups/project-solace/project-solace-before-update-$(date +%F-%H%M).tar.gz instance
```
