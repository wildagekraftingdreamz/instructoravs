@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo Python 3.10 or newer is required and was not found on PATH.
  pause
  exit /b 1
)

rem The virtualenv is created outside this folder on purpose. Some drives cannot
rem execute native binaries stored on them, and a venv is mostly native binaries
rem (python.exe, DLLs). LOCALAPPDATA always runs them. Override with
rem INSTRUCTORAVS_VENV if you want it elsewhere.
if defined INSTRUCTORAVS_VENV (
  set "VENV=%INSTRUCTORAVS_VENV%"
) else (
  set "VENV=%LOCALAPPDATA%\Instructoravs\venv"
)

if not exist "%VENV%\Scripts\python.exe" (
  echo Creating virtualenv in "%VENV%" ...
  python -m venv "%VENV%" || goto :failed
)

set "PY=%VENV%\Scripts\python.exe"
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
