"""
Cached expected-strokes surfaces for the live SG path.

Solving a surface takes ~18s per handicap bracket. To keep API calls fast,
surfaces are precomputed and cached. The cache is a pickle of
{handicap: Surface} for the six standard brackets [0, 5, 10, 15, 20, 25].

Intermediate handicaps are handled by interpolating between the two nearest
bracket surfaces — expected strokes is smooth in handicap, so linear
interpolation of the solved tables is accurate to within the solver's own
Monte Carlo noise.
"""

from __future__ import annotations

import pickle
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional

import numpy as np

from app.core.expected_strokes import Surface, MAX_YARDS, MAX_PUTT_FT
from app.core.empirical import BRACKETS

_CACHE_PATH = Path(__file__).resolve().parent / "data" / "surfaces.pkl"


@lru_cache(maxsize=1)
def _load_cache() -> Dict[int, Surface]:
    """Load the precomputed surfaces from disk."""
    if not _CACHE_PATH.exists():
        raise FileNotFoundError(
            f"Surface cache not found at {_CACHE_PATH}. "
            f"Run: cd backend && uv run python -c \""
            f"from app.core.surface_cache import precompute; precompute()\""
        )
    with open(_CACHE_PATH, "rb") as f:
        return pickle.load(f)


def get_surface(handicap: float) -> Surface:
    """
    Get the expected-strokes surface for a handicap.

    For exact brackets, returns the precomputed surface directly.
    For intermediate handicaps, interpolates linearly between the two nearest
    bracket surfaces.
    """
    cache = _load_cache()
    h = max(0.0, min(float(handicap), 25.0))

    # Exact bracket
    if int(h) in cache and h == int(h):
        return cache[int(h)]

    # Find nearest brackets
    lower = max(b for b in BRACKETS if b <= h)
    upper = min(b for b in BRACKETS if b >= h)

    if lower == upper:
        return cache[lower]

    t = (h - lower) / (upper - lower)
    s_lo = cache[lower]
    s_hi = cache[upper]

    # Interpolate the tables
    green = s_lo.green_ft + t * (s_hi.green_ft - s_lo.green_ft)
    full = {}
    for lie in s_lo.full:
        full[lie] = s_lo.full[lie] + t * (s_hi.full[lie] - s_lo.full[lie])

    # Use the lower-bracket dispersion as a base; the dispersion object is
    # only carried for reference, not used in strokes() lookups on the
    # interpolated surface.
    return Surface(green_ft=green, full=full, dispersion=s_lo.dispersion)


def precompute():
    """Precompute and cache all bracket surfaces. Takes ~2 minutes."""
    from app.core.expected_strokes import calibrate

    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)

    cache = {}
    for h in BRACKETS:
        surface, _ = calibrate(h)
        cache[h] = surface
        print(f"  hcp {h:2d}: done")

    with open(_CACHE_PATH, "wb") as f:
        pickle.dump(cache, f)
    print(f"Cached {len(cache)} surfaces to {_CACHE_PATH}")
