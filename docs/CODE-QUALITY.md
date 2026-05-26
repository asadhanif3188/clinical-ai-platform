# Code Quality & Testing Guide

## 1. Automated (Pre-Commit)
The pre-commit hooks run automatically every time you try to commit changes. If a check fails, the commit is blocked until you fix the issue.

*   **Setup (Run this once per environment):**
    ```bash
    uv run pre-commit install
    ```
*   **Trigger:** Checks automatically run on staged files when you execute `git commit`.
*   **Run manually on all files:**
    ```bash
    uv run pre-commit run --all-files
    ```

## 2. Manual (Makefile)
For a quick, unified check, use the defined `Makefile` target. This runs checks in the project-standard sequence:
```bash
make check
```
*(Runs: ruff check → ruff format → mypy → pytest)*

## 3. Tool-Specific Commands
If you need to isolate a specific tool (e.g., to fix linting or typing errors):

### Linting & Formatting (Ruff)
- **Check for lint errors:** `uv run ruff check .`
- **Automatically fix errors:** `uv run ruff check . --fix`
- **Check formatting:** `uv run ruff format --check .`
- **Apply formatting:** `uv run ruff format .`

### Type Checking (Mypy)
- **Run strict type checks:**
  ```bash
  uv run mypy packages/ api/ --strict
  ```

### Troubleshooting
- **Permission Errors:** If you encounter "Permission denied" or "Access is denied" on Windows, ensure your IDE or other processes aren't locking files in the `.cache/pre-commit` directory.
- **Environment Sync:** If tools are missing, ensure your environment is up-to-date:
  ```bash
  uv sync
  ```
