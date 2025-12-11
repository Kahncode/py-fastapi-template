@echo off
SETLOCAL

REM Save current directory and move to project root
SET SCRIPT_DIR=%~dp0
SET PROJECT_ROOT=%SCRIPT_DIR%..
PUSHD %PROJECT_ROOT%
ECHO Initializing project in %PROJECT_ROOT%

REM Create virtual environment if it doesn't exist
IF NOT EXIST ".venv" (
    python -m venv .venv
    ECHO Virtual environment created at .venv
)

REM Activate virtual environment
CALL .venv\Scripts\activate.bat

REM Upgrade pip
python -m pip install --upgrade pip

REM Install requirements from root and all subfolders
FOR /R %%F IN (requirements.txt) DO (
    IF EXIST "%%F" (
        ECHO Installing requirements from %%F
        pip install -r "%%F"
    )
)

FOR /R %%F IN (requirements-dev.txt) DO (
    IF EXIST "%%F" (
        ECHO Installing requirements from %%F
        pip install -r "%%F"
    )
)

REM Install pre-commit hooks
pre-commit install --install-hooks
pre-commit autoupdate

POPD
ECHO Project environment initialized successfully!
ECHO To activate the virtual environment, run: call .venv\Scripts\activate.bat
