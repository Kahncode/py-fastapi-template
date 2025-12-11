#!/bin/bash
set -e

# Save script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"


# Move to project root
cd "$PROJECT_ROOT"
echo "Initializing project in $PROJECT_ROOT"

if [ -z "$CI" ]; then
    # Create virtual environment if it doesn't exist
    PYTHON_BIN="${PYTHON_BIN:-python3.13}"
    if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
        echo "ERROR: $PYTHON_BIN not found. Install Python 3.13+ or set PYTHON_BIN." >&2
        exit 1
    fi
    if [ ! -d ".venv" ] || ! .venv/bin/python -c 'import sys;print(sys.version_info[:2] >= (3,13))' | grep -q True; then
        rm -rf .venv
        "$PYTHON_BIN" -m venv .venv
        echo "Virtual environment created at .venv"
    fi
    # Activate virtual environment
    source .venv/bin/activate
else
    echo "CI environment detected: skipping venv creation and activation."
fi

# Upgrade pip
python -m pip install --upgrade pip

# Install requirements from root and all subfolders
find . -type f -name requirements.txt | while read reqfile; do
    echo "Installing requirements from $reqfile"
    pip install -r "$reqfile"
done

find . -type f -name requirements-dev.txt | while read reqfile; do
    echo "Installing requirements from $reqfile"
    pip install -r "$reqfile"
done

if [ -z "$CI" ]; then
    # Install pre-commit hooks
    pre-commit install --install-hooks
    pre-commit autoupdate

    echo "Project environment initialized successfully!"
    echo "To activate the virtual environment, run: source .venv/bin/activate"
fi
