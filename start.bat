@echo off
setlocal enabledelayedexpansion

echo =========================================
echo    Klados 1-Click Startup (Windows)
echo =========================================

set "PROJECT_DIR=%~dp0"
if "%PROJECT_DIR:~-1%"=="\" set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"
set "BACKEND_DIR=%PROJECT_DIR%\backend"

:: Prefer the backend's Windows venv when present; plain `python` otherwise.
set "PYTHON=python"
if exist "%BACKEND_DIR%\.venv-windows\Scripts\python.exe" set "PYTHON=%BACKEND_DIR%\.venv-windows\Scripts\python.exe"

:: 1. Verify Docker is running
echo [1/5] Verifying Docker daemon...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Docker daemon is not running.
    echo Please start Docker Desktop and ensure the engine is ready.
    exit /b 1
)
echo Docker is running.

:: 2. Start PostgreSQL and Redis
echo [2/5] Starting PostgreSQL and Redis containers...
cd /d "%PROJECT_DIR%"
docker compose up -d postgres redis
if %errorlevel% neq 0 (
    echo ERROR: Failed to start Docker services.
    exit /b 1
)

:: Wait for PostgreSQL to be healthy
echo Waiting for PostgreSQL to be ready on port 5433...
set RETRY=0
:WAIT_POSTGRES
docker exec klados_postgres pg_isready -U postgres -d leads_db >nul 2>&1
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
cd /d "%BACKEND_DIR%"
"%PYTHON%" -m alembic upgrade head
if %errorlevel% neq 0 (
    echo WARNING: Alembic migrations encountered an issue. Check output above.
)

:: 4. Start RQ worker
echo [4/5] Starting RQ queue worker...
where wsl >nul 2>&1
if %errorlevel% equ 0 (
    echo Starting worker in WSLg namespace wrapper...
    for /f "delims=" %%P in ('wsl wslpath -a "%BACKEND_DIR%"') do set "WSL_BACKEND_DIR=%%P"
    start "Klados Worker" wsl -e bash -c "cd '!WSL_BACKEND_DIR!' && source .venv-linux/bin/activate && chmod +x run_camoufox.sh && ./run_camoufox.sh python -m app.worker"
) else (
    echo WSL not detected. Starting native Python worker...
    start "Klados Worker" cmd /k "cd /d "%BACKEND_DIR%" && "%PYTHON%" -m app.worker"
)

:: 5. Start FastAPI backend
echo [5/5] Starting FastAPI backend on port 8000...
start "Klados API" cmd /k "cd /d "%BACKEND_DIR%" && "%PYTHON%" -m uvicorn app.main:app --host 0.0.0.0 --port 8000"

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
