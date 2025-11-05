@echo off
REM Script para iniciar el servidor web FastAPI

set PYTHONPATH=%~dp0
python server/web_server.py

