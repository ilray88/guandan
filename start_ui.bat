@echo off
REM Start the FableDan GuanDan web UI server.
REM Open http://localhost:8000 after it starts.
cd /d "%~dp0"
.venv\Scripts\python.exe -m uvicorn ui.server:app --host 0.0.0.0 --port 8000
pause