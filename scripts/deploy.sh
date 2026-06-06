#!/usr/bin/env bash
set -euo pipefail

# Pull the latest code from GitHub and restart Project Solace.
# Run from the project-solace directory on your server.

if [ ! -f "docker-compose.yml" ]; then
  echo "Run this script from the project-solace directory."
  exit 1
fi

mkdir -p backups
if [ -f "instance/solace.db" ]; then
  stamp="$(date +%Y%m%d-%H%M%S)"
  cp instance/solace.db "backups/solace-before-deploy-${stamp}.db"
  echo "Database backup created: backups/solace-before-deploy-${stamp}.db"
fi

git pull

docker compose up -d --build

docker compose ps
