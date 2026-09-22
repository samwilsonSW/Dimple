# Dimple Task Board

> **Pick a task. Build it. Mark it done.**
> Current state lives in `STATUS.md`; this board is only unclaimed work.

---

## Active

### 1. Rolling handicap index (server-owned)
**Status:** Next up after the SG rework (PR #23) merges — agreed 2026-09-02.
**What:** `handicap_index` arrives on the round payload and is never
recomputed, so the SG bracket stays frozen at whatever the client sends. If
the player improves, they play "above baseline" forever and zero-mean breaks.
Compute it WHS-style on the server: differential =
(adjusted gross − course rating) × 113 / slope, best 8 of last 20 with the
WHS small-sample table below 20 differentials. Recompute after every posted
round; the SG bracket and baselines read the live index, the client only
displays it. Handicap *trend* = progress; SG = fingerprint at current level.
Rating/slope already live on `tee_box` (both Optional — skip the
differential when absent; 9-hole rounds use the existing prorate). Verify
manual course entry captures rating/slope.
**Where:** new `backend/app/core/handicap.py`; round submit path in
`main.py`; `scorecard_stats.py` L273–280 already computes the same expected-
score shape. `API_CONTRACT.md` first, per convention.
**Done when:** posting a round updates the stored index, the next round's SG
uses it, and a pytest with a fabricated improving sequence walks the index
down.

### 2. Strokes-gained level calibration
**Status:** Ready to start — method agreed 2026-09-02.
**What:** The surface under-counts putts, so bracket-average rounds total
−2 (scratch) to −9 (25 hcp). Constrain the on-green landing distribution with
first-putt-distance-on-GIR by handicap, and fit the putt lag model to
published three-putt rates. Data source: transcribe the Shot Scope charts
(they publish as images); with no user base yet, self-calibration is a later
option, and n=1 calibration to the sole current user is circular by design.
**Where:** `backend/app/core/dispersion.py`, `expected_strokes.py`,
`published.py`; judged by `scripts/solve_baselines.py` holdouts and the
report section of `scripts/verify_sg.py`.
**Done when:** the reality-alignment table in `verify_sg.py` reads near zero
and `avg_score` stays a holdout.

### 3. Shot-by-shot path onto the surface
**Status:** Unstarted. Small branch after the SG rework merges.
**What:** Detailed ingestion in `main.py` still computes per-shot SG from the
retired hand-typed `baselines.py` (fails `audit_sg.py` 4/8) plus a flat
putts-per-hole. Swap to the surface: per-shot SG = E(before) − 1 − E(after),
`get_category()` for the four-way split. Then delete `baselines.py`,
`baseline_fit.py`, `fit_baselines.py`, `audit_sg.py` in the same change —
they exist to indict tables that stop existing.
**Done when:** a round entered hole-by-hole and shot-by-shot produces the
same four totals, and the old tables are gone.

### 4. Verify coach streaming live
**Status:** Implemented, never exercised against the live server or device.
**What:** `POST /coach/chat/stream` (SSE) exists to beat Cloudflare's 100s
524 ceiling; the line-tagged reply format (`coach_format.py`) replaced JSON.
**Done when:** a long coach reply streams to the iOS app on device through
the tunnel without a 524.

---

## Backlog

- launchd service for the backend (manual tmux `dimple-server` today)
- P↔A transfer at 15–25 hcp: replace the analytic reconstruction with the
  SG_REBUILD phase-3 per-hole sampler; drop the 1.25 ceiling in
  `verify_sg.py` to 0.35 when it lands
- Submit idempotency (`client_round_id` + unique constraint)
- Swipe-to-delete (needs backend DELETE endpoint)
- Re-enter pre-migration-020 rounds (102/103/110) from 18birdies
- Coach context memory (PR #16, parked until streaming is verified)

---

## Done (recent)

- [x] SG consistency rework — attribution from the surface's own
  conditionals, CI-gated (`feature/sg-consistency-rework`, 2026-09-02)
- [x] Repo cleanup: fabricated `broadie.py`, discredited `generator.py` +
  reflection tooling, June-era `cli/`, stale branches (2026-09-02)
- [x] Four-category SG live (PR #20) + 9-hole handicap prorate (PR #21)
- [x] Coach streaming + null-safe round stats (on Kanary, unverified live)
- [x] v1.0.0 shipped 2026-08-22 — course search, scorecard, history + stats,
  coach chat, manual course entry, CI

**Dead ends (do not revive):** Expo as shipping frontend (coach lab only),
Chrollo orchestration, hand-typed SG baselines, synthetic round generator.
