"""Helper script to start the FastAPI server using the installed packages."""

import os
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
PACKAGES_DIR = ROOT_DIR / ".packages"
APP_DIR = ROOT_DIR / "ai-link-analysis"

if str(PACKAGES_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGES_DIR))
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import uvicorn  # noqa: E402

if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app.main:app", host=host, port=port, log_level="info")

