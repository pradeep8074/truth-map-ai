@echo off
title TRUTHMAP AI — Local Launcher
echo ========================================================
echo        TRUTHMAP AI — Local Development Services
echo ========================================================
echo.

echo [1/3] Checking environment...
if not exist "backend" (
    echo [ERROR] Must run this script from the truthmap-ai root folder.
    pause
    exit /b 1
)

echo [2/3] Launching FastAPI Backend (Port 8000)...
start "TRUTHMAP AI — Backend (Port 8000)" cmd /k "python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload"

echo [3/3] Launching Vite Frontend (Port 5173)...
start "TRUTHMAP AI — Frontend (Port 5173)" cmd /k "cd frontend && npm run dev"

echo.
echo All services launched!
echo - Backend API:  http://127.0.0.1:8000
echo - API Docs:     http://127.0.0.1:8000/docs
echo - Frontend UI:  http://localhost:5173
echo.
echo Opening browser in 3 seconds...
timeout /t 3 >nul
start http://localhost:5173
echo.
echo Press any key to exit this launcher window (services keep running).
pause >nul
