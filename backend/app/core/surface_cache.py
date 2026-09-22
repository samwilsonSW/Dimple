"""
Cached expected-strokes surfaces and scorecard conditionals for the live SG path.

Solving a surface takes ~18s per handicap bracket, and the scorecard
conditionals add simulation on top. To keep API calls fast, both are
precomputed and cached: a pickle of {handicap: {"surface": Surface,
"cond": HoleConditionals}} for the six standard brackets [0, 5, 10, 15, 20, 25].

Intermediate handicaps are handled by interpolating between the two nearest
bracket entries — expected strokes and its conditionals are smooth in handicap,
so linear interpolation of the solved tables is accurate to within the solver's
own Monte Carlo noise.

The cache file is versioned (`surfaces_v2.pkl`): v1 held bare surfaces and
predates the conditionals, and loading it silently would recreate the exact
attribution drift the conditionals exist to prevent.
"""

from __future__ import annotations

import pickle
from functools import lru_cache
from pathlib import Path
from typing import Dict

import numpy as np

from app.core.expected_strokes import (
    HoleConditionals,
    Surface,
    solve_conditionals,
)
from app.core.empirical import BRACKETS

_CACHE_PATH = Path(__file__).resolve().parent / "data" / "surfaces_v2.pkl"


@lru_cache(maxsize=1)
def _load_cache() -> Dict[int, Dict[str, object]]:
    """Load the precomputed surfaces and conditionals from disk."""
    if not _CACHE_PATH.exists():
        raise FileNotFoundError(
            f"Surface cache not found at {_CACHE_PATH}. "
            f"Run: cd backend && uv run python -c \""
            f"from app.core.surface_cache import precompute; precompute()\""
        )
    with open(_CACHE_PATH, "rb") as f:
        return pickle.load(f)


def _bracket_weights(handicap: float):
    """Clamp to the solved range and return (lower, upper, blend)."""
    h = max(0.0, min(float(handicap), 25.0))
    lower = max(b for b in BRACKETS if b <= h)
    upper = min(b for b in BRACKETS if b >= h)
    t = 0.0 if lower == upper else (h - lower) / (upper - lower)
    return lower, upper, t


def get_surface(handicap: float) -> Surface:
    """
    Get the expected-strokes surface for a handicap.

    For exact brackets, returns the precomputed surface directly.
    For intermediate handicaps, interpolates linearly between the two nearest
    bracket surfaces.
    """
    cache = _load_cache()
    lower, upper, t = _bracket_weights(handicap)

    s_lo: Surface = cache[lower]["surface"]
    if t == 0.0:
        return s_lo
    s_hi: Surface = cache[upper]["surface"]

    green = s_lo.green_ft + t * (s_hi.green_ft - s_lo.green_ft)
    full = {}
    for lie in s_lo.full:
        full[lie] = s_lo.full[lie] + t * (s_hi.full[lie] - s_lo.full[lie])

    # The dispersion object is carried for reference only; strokes() lookups on
    # an interpolated surface never consult it.
    return Surface(green_ft=green, full=full, dispersion=s_lo.dispersion)


def get_conditionals(handicap: float) -> HoleConditionals:
    """Scorecard conditionals for a handicap, interpolated like the surface."""
    cache = _load_cache()
    lower, upper, t = _bracket_weights(handicap)

    c_lo: HoleConditionals = cache[lower]["cond"]
    if t == 0.0:
        return c_lo
    c_hi: HoleConditionals = cache[upper]["cond"]

    def blend(a: Dict[int, np.ndarray], b: Dict[int, np.ndarray]) -> Dict[int, np.ndarray]:
        return {par: a[par] + t * (b[par] - a[par]) for par in a}

    def blend_bands(a: Dict[str, float], b: Dict[str, float]) -> Dict[str, float]:
        return {band: a[band] + t * (b[band] - a[band]) for band in a}

    return HoleConditionals(
        p_fw=blend(c_lo.p_fw, c_hi.p_fw),
        v_hit=blend(c_lo.v_hit, c_hi.v_hit),
        v_miss=blend(c_lo.v_miss, c_hi.v_miss),
        e_fp_putts_gir=blend(c_lo.e_fp_putts_gir, c_hi.e_fp_putts_gir),
        v_prechip=blend(c_lo.v_prechip, c_hi.v_prechip),
        bucket_gir=blend_bands(c_lo.bucket_gir, c_hi.bucket_gir),
        bucket_chip=blend_bands(c_lo.bucket_chip, c_hi.bucket_chip),
    )


def precompute():
    """Precompute and cache all bracket surfaces and conditionals."""
    from app.core.expected_strokes import calibrate

    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)

    cache: Dict[int, Dict[str, object]] = {}
    for h in BRACKETS:
        surface, _ = calibrate(h)
        cond = solve_conditionals(surface)
        cache[h] = {"surface": surface, "cond": cond}
        print(f"  hcp {h:2d}: surface + conditionals done")

    with open(_CACHE_PATH, "wb") as f:
        pickle.dump(cache, f)
    print(f"Cached {len(cache)} brackets to {_CACHE_PATH}")
