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
docker compose up -d --build
```

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
