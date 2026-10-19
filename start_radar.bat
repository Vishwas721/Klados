@echo off
setlocal
cd /d "%~dp0"

echo Starting Klados stack...
docker compose up --build -d
if errorlevel 1 (
    echo Failed to start the stack. Check the docker compose output above.
    exit /b 1
)

echo.
echo Klados is up:
echo   API:       http://localhost:8000/health
echo   Dashboard: http://localhost:3000
echo.
echo Tail logs with: docker compose logs -f
endlocal
