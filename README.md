# 🚀 FastAPI Starter Project

A clean, opinionated starter template for building APIs with [FastAPI](https://fastapi.tiangolo.com/) in Python.
Use this project as a reference or starting point for your FastAPI or other Python API projects.

For a fully-featured example, refer to the official [Full-Stack FastAPI template](https://github.com/fastapi/full-stack-fastapi-template/).

**Features:**

- Modern Python (3.14+) support
- uv for dependency, venv and python version management
- Pre-configured code quality tools (Black, Ruff, pre-commit)
- Ready-to-use development scripts
- VS Code integration recommendations
- Reuseable "shared" library:
  - Configuration framework
  - Logging framework
  - Unit test framework
  - Useful middlewares
  - GCP / Cloud Run utilities
  - SFTP / GCS / S3 file storage
  - SQL database adapter using sqlalchemy

**Author:** [@kahncode](https://github.com/kahncode)

## Quickstart

1. **Install Python**

   - Download and install Python (latest version) from the official website: [https://www.python.org/downloads/](https://www.python.org/downloads/)
   - Make sure to check "Add Python to PATH" during installation.
   - Verify installation:
     ```sh
     python --version
     ```

2. **Set up the development environment**

   - After pulling the latest changes, run the setup script to update dependencies and configure git hooks:
     ```sh
     bash scripts/setup_dev_env.sh
     ```
   - This script will automatically install Python dependencies and set up pre-commit hooks for code quality.

3. **Run the API locally**

   ```sh
   uvicorn src.main:app --reload --host 0.0.0.0 --port 8080
   ```

4. **Access the interactive API docs**
   - Open [http://localhost:8080/docs](http://localhost:8080/docs) in your browser for Swagger UI.
   - Or [http://localhost:8080/redoc](http://localhost:8080/redoc) for ReDoc.

## Development environment with VS Code

### Running Locally

- Open this folder in [Visual Studio Code](https://code.visualstudio.com/).
- Install the [Python extension for VS Code](https://marketplace.visualstudio.com/items?itemName=ms-python.python).
- Use the built-in debugger:
  - Configure visual studio to select the python interpreter from the venv (Python: Select Interpreter command)
  - Press `F5` and select the "Run FastAPI (uvicorn)" or "Run FastAPI (fastapi run)" configuration from the dropdown.
  - The API will start and you can access the docs as above.
- You can also use the integrated terminal to run commands manually.

### Recommended Extensions

For best development experience, install these extensions:

- [Python (Microsoft)](https://marketplace.visualstudio.com/items?itemName=ms-python.python)
- [Pylance (Microsoft)](https://marketplace.visualstudio.com/items?itemName=ms-python.vscode-pylance)
- [Black Formatter (Microsoft)](https://marketplace.visualstudio.com/items?itemName=ms-python.black-formatter)
- [Ruff (Astral Software)](https://marketplace.visualstudio.com/items?itemName=charliermarsh.ruff)
