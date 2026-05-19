"""
Entry point for running the Dimple API from the project root.

Usage:
    python run.py

This script ensures the backend package is discoverable regardless of
where you run it from.
"""
import sys
import os
from pathlib import Path

# Add the current directory to Python path
project_root = Path(__file__).parent.resolve()
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
        reload_dirs=[str(project_root / "backend")],
    )
