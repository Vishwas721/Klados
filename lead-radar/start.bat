@echo off
setlocal enabledelayedexpansion

echo =========================================
echo    Lead Radar 1-Click Startup (Windows)
echo =========================================

set "ROOT_DIR=%~dp0"
if exist "%ROOT_DIR%lead-radar\backend" (
    set "PROJECT_DIR=%ROOT_DIR%lead-radar"
) else (
    set "PROJECT_DIR=%ROOT_DIR%"
)

cd /d "%PROJECT_DIR%"

:: 1. Verify Docker is running
echo [1/5] Verifying Docker daemon...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Docker daemon is not running.
    echo Please start Docker Desktop and ensure the engine is ready.
    exit /b 1
)
echo Docker is running.

:: 2. Start PostgreSQL and Redis via docker compose in backend\
echo [2/5] Starting PostgreSQL and Redis containers...
cd /d "%PROJECT_DIR%\backend"
docker compose up -d
if %errorlevel% neq 0 (
    echo ERROR: Failed to start Docker services in backend\
    exit /b 1
)

:: Wait for PostgreSQL to be healthy
echo Waiting for PostgreSQL to be ready on port 5433...
set RETRY=0
:WAIT_POSTGRES
docker exec lead_radar_postgres pg_isready -U postgres -d leads_db >nul 2>&1
if %errorlevel% neq 0 (
    set /a RETRY+=1
    if !RETRY! geq 30 (
        echo ERROR: PostgreSQL failed to become ready in time.
        exit /b 1
    )
    timeout /t 1 /nobreak >nul
    goto WAIT_POSTGRES
)
echo PostgreSQL is ready.

:: 3. Run database migrations
echo [3/5] Running database migrations...
cd /d "%PROJECT_DIR%\backend"
where alembic >nul 2>&1
if %errorlevel% equ 0 (
    alembic upgrade head
) else (
    python -m alembic upgrade head
)
if %errorlevel% neq 0 (
    echo WARNING: Alembic migrations encountered an issue. Check output above.
)

:: 4. Start RQ worker
echo [4/5] Starting RQ queue worker...
where wsl >nul 2>&1
if %errorlevel% equ 0 (
    echo Starting worker in WSLg namespace wrapper...
    start "Lead Radar Worker" wsl -e bash -c "cd /mnt/c/klados/lead-radar/backend 2>/dev/null || cd /mnt/c/klados/backend; chmod +x run_camoufox.sh; ./run_camoufox.sh python -m app.worker"
) else (
    echo WSL not detected. Starting native Python worker...
    start "Lead Radar Worker" cmd /k "cd /d %PROJECT_DIR%\backend && python -m app.worker"
)

:: 5. Start FastAPI backend
echo [5/5] Starting FastAPI backend on port 8000...
start "Lead Radar API" cmd /k "cd /d %PROJECT_DIR%\backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"

:: 6. Start Next.js frontend
echo Starting Next.js frontend on port 3000...
echo =========================================
echo   FastAPI:  http://localhost:8000
echo   Frontend: http://localhost:3000
echo   Close windows to terminate services
echo =========================================
cd /d "%PROJECT_DIR%\frontend"
npm run dev

endlocal
