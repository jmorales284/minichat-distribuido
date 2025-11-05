@echo off
REM Script para iniciar el cliente
REM Uso: start_client.bat <usuario> <sala> [host:puerto]

set PYTHONPATH=%~dp0
python client/client.py %*

