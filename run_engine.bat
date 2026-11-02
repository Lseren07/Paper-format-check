@echo off
rem Local dev launcher: read .env from repo root, then start engine on 127.0.0.1:8010.
rem The shared key lives only in .env (gitignored) -- never in this file.
rem NOTE: keep this file ASCII-only. cmd.exe reads .bat as ANSI; UTF-8 Chinese
rem comments break line parsing on a GBK console.

setlocal enabledelayedexpansion
cd /d "%~dp0"

if not exist ".env" (
  echo [ERROR] .env not found. Run: copy .env.example .env, then fill FORMAT_ENGINE_KEY.
  exit /b 1
)

rem Read KEY=VALUE lines, skip comments (#) and empty lines.
rem Do NOT add usebackq here: it would treat the quoted filename as a command.
for /f "eol=# tokens=1,* delims==" %%A in (.env) do (
  if not "%%~A"=="" set "%%~A=%%~B"
)

if "%FORMAT_ENGINE_KEY%"=="" (
  echo [ERROR] FORMAT_ENGINE_KEY is empty in .env. The engine refuses to start without it.
  exit /b 1
)

rem Interpreter priority: %PYTHON% -> backend\.venv -> .venv -> python on PATH
set "PY="
if defined PYTHON set "PY=%PYTHON%"
if not defined PY if exist "backend\.venv\Scripts\python.exe" set "PY=backend\.venv\Scripts\python.exe"
if not defined PY if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
if not defined PY set "PY=python"

echo Starting engine on http://127.0.0.1:8010 with "%PY%" ...
"%PY%" -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8010

endlocal
