#!/bin/bash
set -e

# Save script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"


# Move to project root
cd "$PROJECT_ROOT"
echo "Initializing project in $PROJECT_ROOT"

if [ -z "$CI" ]; then
    # Find a suitable python executable to install uv
    if command -v python3 >/dev/null 2>&1; then
        PYTHON_BIN="python3"
    elif command -v python >/dev/null 2>&1; then
        PYTHON_BIN="python"
    else
        echo "ERROR: No python executable found. Please install Python to bootstrap uv." >&2
        exit 1
    fi

    # Ensure uv is installed and up to date
    echo "Ensuring uv is installed and up to date using $PYTHON_BIN..."
    "$PYTHON_BIN" -m pip install --upgrade uv

    # Install dependencies using uv sync
    echo "Installing dependencies..."
    uv sync
    
    # Activate virtual environment
    source .venv/bin/activate
else
    echo "CI environment detected: skipping venv creation and activation."
    # In CI, we assume uv is setup by the workflow, but we need to sync
    uv sync
fi

if [ -z "$CI" ]; then
    # Install pre-commit hooks
    pre-commit install --install-hooks
    pre-commit autoupdate

    echo "Project environment initialized successfully!"
    echo "To activate the virtual environment, run: source .venv/bin/activate"
fi
