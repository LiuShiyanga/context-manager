@echo off
setlocal
cd /d "%~dp0"
uv sync --extra dev || exit /b 1
uv run uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
