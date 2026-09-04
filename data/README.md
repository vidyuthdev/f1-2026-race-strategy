# Derived datasets

These CSVs are committed so that every statistic in the paper can be reproduced without
network access. Run `python src/statistics.py` to re-derive the confidence intervals from
them directly.

All times are in **seconds**. Simulated panels use `SEED = 42` and are deterministic.

---

## `clean_laps.csv` — 5,564 rows

Lap-level 2025 race telemetry, after filtering to representative green-flag racing laps.
This is the only file derived from an external API; everything else is simulator output.

**Source:** FastF1 race sessions for eight 2025 high-speed races.
**Produced by:** `src/undercut_a7.ipynb`, cell 2 (fetches via FastF1, then caches to this
file; on later runs it reads the CSV back instead of re-fetching).
**Filtering:** accurate laps only, pit in/out laps and safety-car laps excluded, and
per-track slow-lap trimming.

| Column | Meaning |
| --- | --- |
| `Driver` | Three-letter driver code (21 drivers) |
| `LapNumber` | Lap index within the race — proxy for fuel load |
| `Compound` | `SOFT` (674 laps) / `MEDIUM` (2,452) / `HARD` (2,438) |
| `TyreLife` | Laps on the current set — the degradation regressor |
| `Stint` | Stint index for the driver |
| `LapTime` | Raw pandas timedelta as returned by FastF1 |
| `LapTimeS` | Lap time in seconds — the regression response |
| `PitInTime`, `PitOutTime` | Pit timestamps where applicable, else null |
| `TrackStatus` | FastF1 track-status flag |
| `IsAccurate` | FastF1 lap-quality flag |
| `Track` | Race label as requested from FastF1 |
| `Pitted` | 1 if the driver pitted on this lap |

---

## `paired_races.csv` — 1,000 rows

Paired comparison of the same race simulated with the 2026 energy layer off and on.
Pairing on identical safety-car draws removes between-race variance.

**Produced by:** `src/master_analysis.ipynb`, cell 13.

| Column | Meaning |
| --- | --- |
| `race` | Race index 0–999 (the pairing key) |
| `t_pre` | Total race time, energy layer **off** |
| `t_2026` | Total race time, energy layer **on** |
| `delta` | `t_pre - t_2026` — seconds saved by the 2026 rules |
| `had_sc` | Whether this race drew at least one safety car (537 of 1,000) |
| `n_sc_laps` | Number of safety-car laps drawn |

---

## `policy_races.csv` — 1,000 rows

Adaptive SDP policy against a fixed-lap plan, over the same 1,000 seeded races.

**Produced by:** `src/master_analysis.ipynb`, cell 15.

| Column | Meaning |
| --- | --- |
| `race` | Race index 0–999 — shares the seed stream with `paired_races.csv`, so rows join on this key |
| `t_adaptive` | Race time under the adaptive policy (with the energy layer) |
| `t_fixed` | Race time under a fixed lap-24 stop (without the energy layer) |

> **Note when using this file.** `t_fixed` has no energy layer, so `t_fixed - t_adaptive`
> (mean +2.46 s) measures adaptivity *and* the 2026 rules together. `t_adaptive` here is
> identical to `t_2026` in `paired_races.csv`, so subtracting that file's `delta`
> (mean +0.69 s) isolates adaptivity alone at +1.77 s. See the README's key results.

---

## `circuit_races.csv` — 4,000 rows

The paired battery comparison repeated across four circuits, 1,000 races each.

**Produced by:** `src/master_analysis.ipynb`, cell 17.

| Column | Meaning |
| --- | --- |
| `circuit` | Monza (53 laps), Spa (44), Silverstone (52), Suzuka (53) |
| `delta` | Seconds saved by the 2026 energy layer in that race |
| `had_sc` | Whether a safety car was drawn |

> `src/statistics.py` reports per-circuit intervals over **all** races in this file;
> `master_analysis.ipynb` reports them over the **safety-car subset** only. Both are
> correct for what they measure, but the numbers differ (e.g. Monza +0.68 vs +1.28) and
> are written to different JSON files.

---

## `b0_sweep.csv` — 5 rows

Sensitivity of the clean-race battery effect to the starting charge `b0`.

**Produced by:** `src/master_analysis.ipynb`, cell 11.

| Column | Meaning |
| --- | --- |
| `b0` | Starting battery charge, 0–4 MJ-equivalent units |
| `delta_green` | Mean seconds saved in clean (no safety car) races |

The relationship is exactly `delta_green = b0 x 0.4`, which is what establishes that any
clean-race "benefit" is just free starting charge rather than a regulatory effect. The
analysis therefore fixes `b0 = 0`.

---

## Not yet produced: `validation.csv`

`src/statistics.py` (section 5) and `src/master_analysis.ipynb` (cell 32) both look for
`data/validation.csv` with columns `model_lap` and `actual_lap`, and skip their
model-vs-actual inference when it is absent — which is the current state. The underlying
comparison is computed and plotted in `src/validationtesting.ipynb`, but that notebook
does not yet export it to CSV.
