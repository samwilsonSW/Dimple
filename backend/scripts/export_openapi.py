#!/usr/bin/env python3
"""Export the FastAPI schema to docs/openapi.json.

Shapes are generated, never hand-written — see AGENTS.md. Run this after
changing any Pydantic model or route, and commit the result alongside the code
change. `smoke_test.py` fails if the committed file is stale.

Usage:
    cd backend && python scripts/export_openapi.py
    cd backend && python scripts/export_openapi.py --check   # exit 1 if stale

Runs without credentials and without the ML stack. Only fastapi, pydantic and
pydantic-settings are genuinely required; heavy or network-bound modules are
stubbed *only when not installed*, so a full environment uses the real ones.

The stubs exist because app/services/embeddings.py instantiates
SentenceTransformer at module scope, so importing the app would otherwise load
a transformer model just to read route metadata.
"""
import argparse
import json
import os
import sys
import types
from pathlib import Path

BACKEND_DIR = Path(__file__).parent.parent.resolve()
PROJECT_ROOT = BACKEND_DIR.parent
OUTPUT = PROJECT_ROOT / "docs" / "openapi.json"

# Settings fields are required with no defaults; import fails without them.
# Never used for I/O — the export only reads route metadata.
_PLACEHOLDERS = {
    "SUPABASE_URL": "https://placeholder.supabase.co",
    "SUPABASE_KEY": "placeholder-key-for-schema-export",
    "MOONSHOT_API_KEY": "placeholder-key-for-schema-export",
}


class _Any:
    """Stand-in that is a real class, so it survives typing annotations."""

    def __init__(self, *args, **kwargs):
        pass

    def __getattr__(self, name):
        return _Any()

    def __call__(self, *args, **kwargs):
        return _Any()


def _stub(name: str, _force: bool = False, **attrs) -> None:
    """Register a stub module.

    Skipped when the real module is importable, unless `_force` — used for
    modules whose import has side effects we never want in tooling.
    """
    if not _force:
        try:
            __import__(name)
            return
        except ImportError:
            pass

    module = types.ModuleType(name)
    module.__all__ = list(attrs)
    # Treat every stub as a package so submodule imports resolve.
    module.__path__ = []
    for attr, value in attrs.items():
        setattr(module, attr, value)

    def _missing(attr, _name=name):
        # Dunders must still fail, or the import machinery misreads the stub.
        if attr.startswith("__") and attr.endswith("__"):
            raise AttributeError(f"{_name}.{attr}")
        return _Any()

    module.__getattr__ = _missing
    sys.modules[name] = module

    parent, _, child = name.rpartition(".")
    if parent:
        _stub(parent)
        setattr(sys.modules[parent], child, module)


def prepare_imports() -> None:
    """Make `app.*` importable without credentials or the ML stack.

    Shared with smoke_test.py. Safe to call more than once.
    """
    for key, value in _PLACEHOLDERS.items():
        os.environ.setdefault(key, value)

    # Always stubbed. The model loads lazily now, so importing it is safe — but
    # pulling in torch costs ~25s, and reading route metadata never needs real
    # embeddings. Forcing the stub keeps tooling fast and keeps it working in
    # environments where the ML stack was never installed at all.
    _stub("sentence_transformers", _force=True, SentenceTransformer=_Any)
    _stub("numpy")
    _stub("openai", OpenAI=_Any)
    _stub("supabase", create_client=lambda *a, **k: _Any(), Client=_Any)
    _stub("supabase.lib.client_options", SyncClientOptions=_Any)
    _stub("requests")
    _stub("httpx", Client=_Any, Limits=_Any, Timeout=_Any)

    for path in (str(BACKEND_DIR), str(PROJECT_ROOT)):
        if path not in sys.path:
            sys.path.insert(0, path)


def build_schema() -> dict:
    prepare_imports()

    from app.main import app

    schema = app.openapi()
    # Stable ordering keeps diffs reviewable.
    return json.loads(json.dumps(schema, sort_keys=True))


def render(schema: dict) -> str:
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the committed file is current; do not write",
    )
    args = parser.parse_args()

    rendered = render(build_schema())
    relative = OUTPUT.relative_to(PROJECT_ROOT)

    if args.check:
        if not OUTPUT.exists():
            print(f"MISSING  {relative}")
            print("         run: python scripts/export_openapi.py")
            return 1
        if OUTPUT.read_text() != rendered:
            print(f"STALE    {relative}")
            print("         the schema changed but the file was not regenerated")
            print("         run: python scripts/export_openapi.py")
            return 1
        print(f"current  {relative}")
        return 0

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    existing = OUTPUT.read_text() if OUTPUT.exists() else None
    OUTPUT.write_text(rendered)
    print(f"{'unchanged' if existing == rendered else 'written'}  {relative}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
