#!/usr/bin/env bash
set -euo pipefail

# Create a timestamped local SQLite backup.
# Run from the project-solace directory.

if [ ! -f "instance/solace.db" ]; then
  echo "No database found at instance/solace.db"
  exit 1
fi

mkdir -p backups
stamp="$(date +%Y%m%d-%H%M%S)"
cp instance/solace.db "backups/solace-${stamp}.db"
echo "Backup created: backups/solace-${stamp}.db"
