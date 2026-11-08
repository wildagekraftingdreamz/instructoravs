@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo Python 3.10 or newer is required and was not found on PATH.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating .venv ...
  python -m venv .venv || goto :failed
)

set "PY=.venv\Scripts\python.exe"
"%PY%" -c "import fastapi, uvicorn" >nul 2>nul
if errorlevel 1 (
  echo Installing studio dependencies ...
  "%PY%" -m pip install --disable-pip-version-check -q -r requirements.txt || goto :failed
)

"%PY%" -m app %*
exit /b %errorlevel%

:failed
echo.
echo Startup failed. See the message above.
pause
exit /b 1
