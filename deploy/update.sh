#!/usr/bin/env bash
# Update VCP Screener on VM to latest code
# Run on VM: bash deploy/update.sh
set -euo pipefail

cd "$HOME/vcp-screener"

echo "Pulling latest code..."
git pull

echo "Rebuilding Docker images..."
docker compose build

echo "Restarting services..."
docker compose down
docker compose up -d

echo "Update complete. Checking service health..."
sleep 10
docker compose ps
