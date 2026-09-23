#!/usr/bin/env bash

# ─────────────────────────────────────────────────────────────────────────────
# STEP 0 ── WSL Bounce
#
# If this script is running inside Git Bash on Windows (MSYSTEM is set, e.g.
# MINGW64), Linux-specific commands like `unshare`, `venv/bin/activate`, etc.
# will fail.  Detect this early and re-execute the exact same script inside the
# default WSL distro so everything runs natively on Linux.
# ─────────────────────────────────────────────────────────────────────────────
if [ -n "${MSYSTEM:-}" ] || [[ "$(uname -s)" == MINGW* ]] || [[ "$(uname -s)" == CYGWIN* ]]; then
    echo "[WSL Bounce] Detected Git Bash / Mingw environment."
    echo "[WSL Bounce] Re-launching inside WSL..."

    # Convert the Windows path of this script to a WSL path.
    # `wslpath` is only available from inside WSL; use sed to do a simple
    # drive-letter substitution so the wsl -e bash invocation can find it.
    WIN_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    # Git Bash gives paths like /c/klados/... – convert to /mnt/c/klados/...
    WSL_PATH="$(echo "$WIN_PATH" | sed 's|^/\([a-zA-Z]\)/|/mnt/\1/|')"

    exec wsl -e bash "$WSL_PATH/start.sh" "$@"
fi

# ─────────────────────────────────────────────────────────────────────────────
# From here on we are guaranteed to be running inside a real Linux shell.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Resolve project root (repo layout: klados/lead-radar/... OR klados/...)
if [ -d "$SCRIPT_DIR/lead-radar/backend" ]; then
    PROJECT_DIR="$SCRIPT_DIR/lead-radar"
elif [ -d "$SCRIPT_DIR/backend" ]; then
    PROJECT_DIR="$SCRIPT_DIR"
else
    echo "ERROR: Cannot locate a directory containing backend/ under $SCRIPT_DIR"
    exit 1
fi

BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"
VENV_DIR="$BACKEND_DIR/.venv"
LOG_DIR="$PROJECT_DIR/logs"

mkdir -p "$LOG_DIR"

echo "========================================="
echo "   Lead Radar 1-Click Startup"
echo "   Project: $PROJECT_DIR"
echo "========================================="

# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 ── Docker health-check
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo "[1/5] Verifying Docker daemon..."
if ! docker info >/dev/null 2>&1; then
    echo "ERROR: Docker daemon is not running."
    echo "       Start Docker Desktop (Windows) or 'sudo service docker start' (WSL) first."
    exit 1
fi
echo "      Docker is running."

# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 ── Start PostgreSQL & Redis via docker compose
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo "[2/5] Starting PostgreSQL and Redis..."
(cd "$BACKEND_DIR" && docker compose up -d)

echo "      Waiting for PostgreSQL to be healthy (up to 30 s)..."
MAX_WAIT=30
WAITED=0
until docker exec lead_radar_postgres pg_isready -U postgres -d leads_db >/dev/null 2>&1; do
    if [ "$WAITED" -ge "$MAX_WAIT" ]; then
        echo "ERROR: PostgreSQL did not become ready within ${MAX_WAIT} s."
        exit 1
    fi
    sleep 1
    WAITED=$((WAITED + 1))
done
echo "      PostgreSQL is ready (waited ${WAITED} s)."

# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 ── Python virtual environment (Linux venv)
#
# The venv lives at backend/.venv.  If it doesn't exist we create it and
# install all dependencies so subsequent activations (alembic, uvicorn, rq)
# use the right interpreter and packages.
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo "[3a/5] Checking Python virtual environment at $VENV_DIR..."

# Pick the best available Python 3 interpreter
PYTHON_BIN=""
for candidate in python3.11 python3.12 python3.10 python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        PYTHON_BIN="$candidate"
        break
    fi
done
if [ -z "$PYTHON_BIN" ]; then
    echo "ERROR: No Python 3 interpreter found. Install python3 first."
    exit 1
fi

if [ ! -f "$VENV_DIR/bin/activate" ]; then
    echo "       Virtual environment not found – creating it with $PYTHON_BIN..."
    "$PYTHON_BIN" -m venv "$VENV_DIR"
    # shellcheck source=/dev/null
    source "$VENV_DIR/bin/activate"
    echo "       Installing dependencies from requirements.txt..."
    pip install --upgrade pip -q
    pip install -r "$BACKEND_DIR/requirements.txt" -q
    echo "       Dependencies installed."
else
    echo "       Activating existing virtual environment..."
    # shellcheck source=/dev/null
    source "$VENV_DIR/bin/activate"
fi

echo "       Python: $(python --version)"

# ─────────────────────────────────────────────────────────────────────────────
# STEP 3b ── Alembic database migrations
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo "[3b/5] Running database migrations (alembic upgrade head)..."
(cd "$BACKEND_DIR" && alembic upgrade head)
echo "       Migrations applied."

# ─────────────────────────────────────────────────────────────────────────────
# STEP 4 ── Background process management
#
# Background the RQ worker and the FastAPI server using plain Linux `&`.
# stdout/stderr of each are tee'd to log files under logs/ so you can
# inspect them while the frontend runs in the foreground.
#
# The SIGINT / SIGTERM trap (below) kills these PIDs and optionally tears down
# the Docker containers when you hit Ctrl+C.
# ─────────────────────────────────────────────────────────────────────────────
PIDS=()

cleanup() {
    echo ""
    echo "─────────────────────────────────────────"
    echo " Ctrl+C received – shutting down..."
    echo "─────────────────────────────────────────"

    for pid in "${PIDS[@]:-}"; do
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            echo " Stopping PID $pid..."
            kill "$pid" 2>/dev/null || true
        fi
    done

    # Give processes a moment to clean up
    sleep 1
    wait 2>/dev/null || true

    echo " Stopping Docker containers..."
    (cd "$BACKEND_DIR" && docker compose stop) 2>/dev/null || true

    echo " All services stopped. Goodbye."
    # Deactivate venv if still active
    type deactivate >/dev/null 2>&1 && deactivate || true
    exit 0
}

# Catch Ctrl+C, kill, and normal EXIT (EXIT runs cleanup after the
# foreground npm process exits naturally as well).
trap cleanup SIGINT SIGTERM EXIT

# ── 4a: RQ queue worker (background)
echo ""
echo "[4/5] Starting RQ queue worker..."
(
    # Re-activate the venv inside the subshell
    source "$VENV_DIR/bin/activate"
    cd "$BACKEND_DIR"
    export PYTHONPATH="$BACKEND_DIR:${PYTHONPATH:-}"
    # rq worker is the standard way to consume lead_tasks queue
    python -m app.worker
) >"$LOG_DIR/worker.log" 2>&1 &
WORKER_PID=$!
PIDS+=("$WORKER_PID")
echo "       Worker PID $WORKER_PID  →  logs/worker.log"

# ── 4b: FastAPI backend (background)
echo ""
echo "[5/5] Starting FastAPI backend on :8000..."
(
    source "$VENV_DIR/bin/activate"
    cd "$BACKEND_DIR"
    export PYTHONPATH="$BACKEND_DIR:${PYTHONPATH:-}"
    uvicorn app.main:app --host 0.0.0.0 --port 8000
) >"$LOG_DIR/api.log" 2>&1 &
API_PID=$!
PIDS+=("$API_PID")
echo "       API PID $API_PID  →  logs/api.log"

# Brief pause so uvicorn has time to bind before the browser-facing
# frontend tries to hit it.
sleep 2

# ─────────────────────────────────────────────────────────────────────────────
# STEP 5 ── Next.js frontend (foreground)
#
# Running npm in the foreground means the terminal shows Next.js output
# directly.  Ctrl+C here triggers the trap above to clean everything up.
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo "========================================="
echo "  FastAPI  →  http://localhost:8000"
echo "  Frontend →  http://localhost:3000"
echo "  Worker   →  logs/worker.log"
echo "  API      →  logs/api.log"
echo "  Press Ctrl+C to stop all services"
echo "========================================="
echo ""

cd "$FRONTEND_DIR"
npm run dev
