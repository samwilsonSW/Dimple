# Strokes Gained — rebuild plan

> Why the two blank chips in round history cannot be filled without rebuilding
> the baselines first, and what the rebuild is.

Reproduce everything below with:

```bash
cd backend && uv run python scripts/audit_sg.py      # the diagnosis, 4 of 8 failing
cd backend && uv run python scripts/fit_baselines.py # the cheap fix, and why it fails
```

---

## The question that started it

Round history renders four strokes-gained chips per round — `G`, `P`, `F`, `A`.
`P` and `F` show `—` on every round ever logged. They are hardcoded `nil` in
`RoundHistoryView.swift`, marked `// TBD`.

The interesting part is not the missing wiring. It is what the audit found
underneath it.

---

## What is actually wrong

### 1. The baselines are miscalibrated by 5 to 17 strokes

Expected strokes to hole out from the tee, summed over 18 holes, *is* the
expected score. So the tee table can be checked directly against what golfers in
that bracket actually shoot. It does not survive the check:

| handicap | baseline implies | measured | error |
|---:|---:|---:|---:|
| 0 | 69.75 | 74.6 | −4.85 |
| 5 | 71.55 | 79.0 | −7.45 |
| 10 | 74.02 | 84.6 | −10.58 |
| 15 | 76.41 | 89.3 | −12.89 |
| 20 | 78.91 | 93.7 | −14.79 |
| 25 | 81.53 | 98.6 | −17.07 |

A player shooting exactly their bracket average is, by definition, average — the
app should show them SG 0.00. It shows a 25 handicap **−17 strokes**, and the
error grows with handicap, so it is worst for the players the coach exists to
help.

The cause is visible in the table's own header comment: scratch values were
taken as par-like, then "higher handicaps are worse at everything" was applied as
small hand-typed increments. A 400-yard par 4 reads 4.00 strokes at scratch and
4.70 at 25 handicap — a 0.70 spread standing in for a real gap of about 1.33 per
hole.

### 2. The putting table is too generous

Inverting it: what first putt would a player face, every hole, to produce their
measured putts per round? It answers 49 feet for scratch through 20 handicap. A
realistic average first putt is 20–40 feet, so the table under-counts putts and
SG putting reads systematically flattering.

### 3. Two hole-level proxies do not do what their comments say

Both are arithmetic, both confirmed numerically by check 6:

- **`calculate_sg_approach`, par-4 branch.** `expected_drive` and
  `expected_approach` both contain `baseline.strokes(150, "fairway")` with
  opposite signs. It cancels. The branch is identical to the par-3 branch, and
  the `drive_distance` computed above it is never read.
- **`calculate_sg_putting`, non-GIR branch.** `1.0 + (strokes(15,"green") - 1.0)`
  is a no-op. The comment says it charges a chip stroke; it does not. That stroke
  falls into `score - putts` instead, so **short game is being attributed to the
  approach chip**.

### 4. The app collapses 76% of amateur skill into one number

From the measured aggregates, the scratch-to-25 gap of 24 strokes splits:

- putting — 5.7 strokes (24%), shown as chip `G`
- tee-to-green — 18.3 strokes (76%), shown as chip `A`

Driving and short game make up most of that 76%, and they are the two chips
rendering blank. The one chip that is populated is also silently absorbing the
un-charged chip stroke from §3.

So the blank chips are not a cosmetic gap. They are the majority of the signal.

---

## What we tried, and why it is not enough

`app/core/baseline_fit.py` keeps the existing table shape — which passes the
structural checks (monotone in handicap, monotone in distance, correct
fairway < rough < sand ordering) — and solves one scale factor per bracket:

```
E'(d, lie) = 1 + s · (E(d, lie) − 1)
```

Fit on `avg_score` and `avg_putts`, validated against `gir_pct` and
`up_down_pct` — aggregates the solver never saw.

It hits its anchors exactly and **fails the holdout**: GIR RMSE 0.153 (bias
−0.141), up-and-down RMSE 0.205 (bias −0.204), collapsing to 0.000 at 20 and 25
handicap. One scale makes a player uniformly worse from everywhere, and real
skill is not uniform — the scratch-to-25 gap is enormous from 200 yards in the
rough and nearly nil from three feet. Forcing one factor over both over-penalises
short shots to pay for long ones.

Kept as a recorded dead end. It establishes the fit/holdout harness the real
model has to clear, and rules out the cheap option.

---

## The rebuild

### Phase 1 — Derive baselines from dispersion, not by typing them

Stop hand-authoring expected-strokes tables. Model the physical thing instead —
where a player's shots finish — and let expected strokes fall out.

For each handicap, a small set of *physical* skill parameters:

- driving distance and lateral dispersion (`avg_drive_yards`, `drive_std` are
  already measured; lateral dispersion is pinned by `fairway_pct`)
- approach proximity as a function of distance and lie
- short-game proximity from off the green
- putting make-rate by distance

Then expected strokes to hole out is a recursion solved by value iteration over a
distance × lie grid:

```
E(d, lie) = 1 + E_outcome[ E(d', lie') ]
```

This inverts the current problem. Today we have six measured aggregates and a
whole surface to fill, which is badly underdetermined — hence hand-typing. With a
dispersion model there are roughly a dozen parameters total, and all six
aggregates become *outputs* to fit against. Overdetermined, so the residuals mean
something.

It also fixes §1 and §2 structurally: a surface derived from make-rates and
proximity cannot drift 17 strokes from observed scoring without the fit screaming.

**Needs:** shot-pattern priors. Three sources, in preference order — published
amateur dispersion data; the app's own shot-by-shot rounds once enough exist
(this is the virtuous loop, and matches the product principle in AGENTS.md); or a
documented physical prior with the sensitivity reported, as a stopgap.

### Phase 2 — One SG primitive, with units in the type system

Every SG calculation goes through one function. `strokes(distance, lie)` currently
takes a bare int whose unit depends on the lie — feet on the green, yards
everywhere else. AGENTS.md already lists this as a rule people forget, which is
the definition of a hazard worth removing. Make `Yards` and `Feet` distinct types
so the mix cannot compile.

Fix the two dead-arithmetic bugs from §3 here.

### Phase 3 — Attribute the four categories

Only now is filling `P` and `F` meaningful.

The load-bearing property: per-shot SG **telescopes**. For any reconstructed shot
path,

```
(E_tee − 1 − E₁) + (E₁ − 1 − E₂) + … + (E_k − 1) = E_tee − score
```

Every intermediate term cancels. So any plausible reconstruction sums to exactly
the right hole total; the reconstruction only decides *attribution*. Errors are
compensating across the four buckets rather than accumulating, and no residual
fudge term is needed. That is a far weaker thing to ask of a model than
estimating SG driving from nothing.

For scorecard rounds, sample shot paths consistent with the observed
`par, yardage, score, putts, fairway, gir`, weight them by the dispersion model
from phase 1, and average the per-category attribution. Most latents collapse
analytically — `fairway` gives the lie after the drive, `score − putts` gives the
shot count, `gir` says whether a short-game shot exists. Seed the sampler on
`(round_id, hole_number)` so a stat never changes between refreshes.

`get_category()` in `baselines.py` already implements Broadie's four-way split
and has no callers outside a test. This is where it gets one.

**Signal currently thrown away:** `putts` is treated as an output, but it is
evidence about approach quality. The green table *is* a putts-from-distance
likelihood, so `P(first putt distance | putts, handicap)` is recoverable — a
1-putt says the approach finished close. That is the lever that separates
approach from putting honestly, at no extra cost to the user.

### Phase 4 — Validation that does not depend on the generator

`generator.py` cannot be ground truth. Its `_gir` and `_up_down` re-apply a
handicap penalty on top of already handicap-specific rates, so it does not
reproduce its own inputs; `_approach_dist` has no handicap term at all; `_putts`
rounds a per-hole mean to a near-constant 2. The `HANDICAP_STATS` table inside it
is real measured data and has been lifted into `app/core/empirical.py`. The
sampler around it should not be trusted.

What replaces it:

1. **Conservation** — the four categories must sum to hole SG exactly. Pure
   arithmetic, model-independent.
2. **Held-out aggregates** — fit on some measured aggregates, validate on the
   others. Already wired in `scripts/fit_baselines.py`.
3. **Held-out observables** — compute SG driving *without* being given the
   `fairway` flag, then check it predicts the withheld flag. Predicting a signal
   it was not shown is real evidence, and needs only scorecard data.
4. **Zero-sum** — a bracket playing to its handicap must average SG 0.00. This is
   check 1, and it is the one currently failing by 17 strokes.

### Phase 5 — Surface it

Show `P` and `F` with their confidence, not as bare numbers. An honest ±0.6 is
worth more than a confident fabrication, and on manual-course rounds with no
yardage the driving estimate should be suppressed rather than invented.

Per AGENTS.md this is Sam's call, not an agent's.

---

## Sequencing note

Phases 1 and 2 change every SG number the app displays. AGENTS.md puts anything
that changes what the user sees on Sam's desk, so nothing in this branch is wired
into the live path — it adds diagnosis, an anchor module, and a rejected
candidate. The first behaviour change should be a deliberate, separate merge.

## What is in this branch

| Path | What |
|---|---|
| `backend/app/core/empirical.py` | Measured aggregates, lifted out of `generator.py`. Data only, no simulation. |
| `backend/scripts/audit_sg.py` | The diagnosis, as 8 runnable checks. Exits non-zero; ready to join the smoke test once green. |
| `backend/app/core/baseline_fit.py` | The rescaling candidate and its recorded failure. |
| `backend/scripts/fit_baselines.py` | Fit, holdout, and sensitivity report. |
| `docs/SG_REBUILD.md` | This file. |

No endpoints, models, or migrations were touched, so `openapi.json` is unchanged.
