@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "VENV_PY=%SCRIPT_DIR%.venv\Scripts\python.exe"
set "ENTRY=%SCRIPT_DIR%planer_cli.py"

if not exist "%ENTRY%" (
  echo Startdatei nicht gefunden: %ENTRY%
  pause
  exit /b 1
)

if exist "%VENV_PY%" (
  "%VENV_PY%" "%ENTRY%"
) else (
  py -3 "%ENTRY%"
)

if errorlevel 1 (
  echo.
  echo Das Script konnte nicht gestartet werden.
  pause
)

endlocal
