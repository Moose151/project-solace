#!/usr/bin/env bash
set -euo pipefail

# Pull the latest code from GitHub and restart Project Solace.
# Run from the project-solace directory on your server.

if [ ! -f "docker-compose.yml" ]; then
  echo "Run this script from the project-solace directory."
  exit 1
fi

mkdir -p backups instance
if command -v stat >/dev/null 2>&1; then
  owner="$(stat -c %u instance 2>/dev/null || echo unknown)"
  if [ "$owner" != "1000" ]; then
    echo "Note: the Docker container runs as UID 1000. If startup cannot open the database, run: sudo chown -R 1000:1000 instance"
  fi
fi

if [ -f "instance/solace.db" ]; then
  stamp="$(date +%Y%m%d-%H%M%S)"
  cp instance/solace.db "backups/solace-before-deploy-${stamp}.db"
  echo "Database backup created: backups/solace-before-deploy-${stamp}.db"
fi

git pull

docker compose up -d --build

docker compose ps
