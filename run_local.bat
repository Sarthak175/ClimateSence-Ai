@echo off
REM ClimateSense AI - one command to run locally on Windows.
REM Run from the folder that contains backend\ and frontend\:   run_local.bat
setlocal
cd /d "%~dp0"

if not exist backend\requirements.txt (
  echo [ERROR] backend\requirements.txt not found. Extract the zip completely and run this file from the climatesense-ai folder.
  pause & exit /b 1
)
if not exist backend\models\best_model.joblib (
  echo [ERROR] backend\models\best_model.joblib is missing. Use the latest zip - it contains the trained model.
  pause & exit /b 1
)

echo === 1/4 Backend environment (fresh, only runtime packages) ===
if exist backend\.venv rmdir /s /q backend\.venv
python -m venv backend\.venv || (echo [ERROR] Python 3.10+ is required. & pause & exit /b 1)
call backend\.venv\Scripts\activate.bat
python -m pip install --no-cache-dir -q -r backend\requirements.txt || (echo [ERROR] pip install failed - check disk space on C: & pause & exit /b 1)

echo === 2/4 Frontend packages ===
cd frontend
if not exist node_modules call npm install || (echo [ERROR] npm install failed. & pause & exit /b 1)
cd ..

echo === 3/4 Starting backend on http://localhost:8000 ===
start "ClimateSense backend" cmd /k "cd /d "%~dp0backend" && "%~dp0backend\.venv\Scripts\python.exe" -m uvicorn app.main:app --port 8000"

echo === 4/4 Starting frontend on http://localhost:5173 ===
timeout /t 4 /nobreak >nul
start "" http://localhost:5173
cd frontend && npm run dev -- --port 5173
