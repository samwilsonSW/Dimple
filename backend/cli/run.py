"""
Entry point for running the Dimple API.

Usage:
    python run.py

Works from any directory — auto-discovers the project root.
"""
import sys
import os
from pathlib import Path

# Get the directory containing this script (project root)
project_root = Path(__file__).parent.resolve()
backend_dir = project_root / "backend"

# Add both project root and backend to Python path
# This makes both 'backend.app' and 'app' imports work
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
