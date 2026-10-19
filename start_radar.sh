#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "Starting Klados stack..."
docker compose up --build -d

echo ""
echo "Klados is up:"
echo "  API:       http://localhost:8000/health"
echo "  Dashboard: http://localhost:3000"
echo ""
echo "Tail logs with: docker compose logs -f"
