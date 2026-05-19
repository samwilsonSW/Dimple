"""
Entry point for running the Dimple API.

Usage:
    python run.py

This script ensures the app package is discoverable regardless of
where you run it from (project root, backend folder, etc.).
"""
import sys
import os
from pathlib import Path

# Add the parent directory (project root) to Python path
# This makes 'backend.app' importable from anywhere
project_root = Path(__file__).parent.parent.resolve()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Now import and run
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "backend.app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=[str(Path(__file__).parent)],
    )
