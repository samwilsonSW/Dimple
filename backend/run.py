"""
Entry point for running the Dimple API from the backend folder.

Usage:
    python run.py

Works from the backend directory — adds parent to path for 'backend.app' imports.
"""
import sys
import os
from pathlib import Path

# Get the backend directory
backend_dir = Path(__file__).parent.resolve()
project_root = backend_dir.parent

# Add both backend and project root to Python path
for path in [str(backend_dir), str(project_root)]:
    if path not in sys.path:
        sys.path.insert(0, path)

# Now import and run
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=[str(backend_dir)],
    )
