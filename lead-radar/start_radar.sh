#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "Starting Lead Radar stack..."
docker compose up --build -d

echo ""
echo "Lead Radar is up:"
echo "  API:       http://localhost:8000/health"
echo "  Dashboard: http://localhost:3000"
echo ""
echo "Tail logs with: docker compose logs -f"
