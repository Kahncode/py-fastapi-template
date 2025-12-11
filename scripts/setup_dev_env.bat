@echo off
SETLOCAL

REM Save current directory and move to project root
SET SCRIPT_DIR=%~dp0
SET PROJECT_ROOT=%SCRIPT_DIR%..
PUSHD %PROJECT_ROOT%
ECHO Initializing project in %PROJECT_ROOT%

REM Ensure uv is installed and up to date
ECHO Ensuring uv is installed and up to date...
python -m pip install --upgrade uv

REM Install dependencies using uv sync
ECHO Installing dependencies...
uv sync

REM Install pre-commit hooks
pre-commit install --install-hooks
pre-commit autoupdate

POPD
ECHO Project environment initialized successfully!
ECHO To activate the virtual environment, run: call .venv\Scripts\activate.bat
