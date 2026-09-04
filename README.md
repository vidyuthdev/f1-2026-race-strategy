# Optimal Race Strategy Under the 2026 Formula One Regulations

How do the 2026 Formula One regulations influence optimal race strategy on high-speed
circuits? This project builds an empirically calibrated, stochastic model of an F1 race
and uses it to derive optimal pit-stop, tyre, and energy-deployment strategies — with a
particular focus on the new 2026 electrical-deployment and safety-car recharging rules.

## Data

All data comes from public sources and **the derived CSVs are committed to this
repository**, so every result below can be reproduced without touching a network API.

| Source | Used for | Access |
| --- | --- | --- |
| **FastF1** (2025 race sessions) | Lap times, tyre compound, tyre age, stint and pit data for eight high-speed races → `data/clean_laps.csv` (5,564 clean laps, 21 drivers) | `fastf1` package |
| **OpenF1** (2025 season) | Safety-car and VSC frequency across all 24 races → `safety_car` block of `src/parameters.json` | `api.openf1.org` |
| **FastF1** (2026 race sessions) | Actual pit laps for model-vs-actual validation | `fastf1` package |

The 2025 lap data covers eight races, labelled in the `Track` column of
`data/clean_laps.csv` as: Albert Park, Jeddah, Las Vegas, Monza, Red Bull Ring,
Silverstone, Spa, Suzuka. Compound split is 2,452 MEDIUM / 2,438 HARD / 674 SOFT laps.

Re-fetching from the APIs is only needed if you want to regenerate the calibration from
scratch. FastF1 responses are cached in `src/f1_cache/` (~90 MB, git-ignored, rebuilt
automatically on first run).

## Approach

The model is built up in layers:

1. **Empirical calibration** — tyre-degradation rates, pit-stop time loss, and safety-car
   frequencies are estimated from real 2025 data.
2. **Deterministic baseline** — dynamic programming finds the optimal fixed pit strategy
   assuming no safety cars.
3. **Stochastic dynamic programming (SDP)** — a 5-state geometric-duration Markov chain with a deterministic four-lap countdown that
   models random safety cars, and backward induction yields an adaptive policy.
4. **2026 battery layer** — battery state and energy-management actions (deploy / hold /
   harvest, plus free recharging under safety cars) are added to the state space.
5. **Game theory** — a Stackelberg model of the undercut between two drivers.
6. **Validation** — model predictions are compared against actual 2026 race data.

`src/master_analysis.ipynb` consolidates layers 3–5 into a single end-to-end run and is
the notebook that produces the committed `data/*.csv` and `results/*`. The older
per-layer notebooks are kept because they contain analysis the master notebook does not
reproduce (calibration, the deterministic strategy sweep, the Stackelberg game, and the
2026 validation).

## Repository layout

```
data/                     Committed derived datasets — see data/README.md
  clean_laps.csv            2025 lap-level telemetry (calibration input)
  paired_races.csv          1,000 paired races, battery layer off vs on
  policy_races.csv          1,000 races, adaptive policy vs fixed plan
  circuit_races.csv         1,000 races x 4 circuits
  b0_sweep.csv              Starting-charge sensitivity check
results/
  statistics.json           Headline estimates and CIs (from master_analysis.ipynb)
  fig_*.png                 Result figures
src/
  master_analysis.ipynb   End-to-end run: SDP + battery + statistics + figures
  statistics.py           Standalone re-derivation of the CIs from data/*.csv
  parameters.json         Calibrated model parameters
  pitstops.ipynb          Empirical calibration from 2025 data -> parameters.json
  model0DP.ipynb          Deterministic baseline (dynamic programming)
  markovSDP.ipynb         Stochastic DP with the safety-car Markov chain
  batteryimplement.ipynb  2026 battery / energy-deployment layer
  gametheory.ipynb        Undercut game (Stackelberg)
  highspeedTracks.ipynb   Full model across multiple high-speed circuits
  undercut_a7.ipynb       Tyre regression with circuit fixed effects
  validationtesting.ipynb Validation against 2026 results
images/
  visualizations.ipynb    Figure generation (Markov chain, transition matrix, results)
  *.png                   Exported figures
```

## Reproducing the results

```bash
conda env create -f environment.yml && conda activate f1
# or: python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
```

**From the committed data (no network, seconds):**

```bash
python src/statistics.py
```

This reads `data/*.csv` and reproduces every confidence interval in the paper. It runs
from any working directory and writes `results/statistics_standalone.json`.

**From the model (no network, a few minutes):**

Run `src/master_analysis.ipynb` top to bottom. It reads `src/parameters.json`, re-solves
the DP, re-simulates the 1,000-race panels, and rewrites `data/*.csv` and `results/*`.
All simulations are seeded (`SEED = 42`; bootstrap seed `20260903`), so the outputs are
deterministic.

**From the raw APIs (network required):**

Run `src/pitstops.ipynb` first to regenerate `src/parameters.json` from FastF1 and
OpenF1, then the modelling notebooks in the order listed above.

## Key results

- **The 2026 energy rules do not move the optimal pit lap.** Solving the dynamic program
  with the energy layer disabled and enabled returns the *identical* optimal stop at
  every circuit tested — Monza 23, Spa 20, Silverstone 23, Suzuka 23, and lap 24 at the
  57-lap reference circuit. The new regulations change what a race is *worth*, not when
  to stop. Strategy software calibrated to 2025 pit windows does not need to move them.

- **The battery's value is concentrated entirely in safety-car races.** Averaged over
  1,000 paired races the 2026 layer is worth **+0.69 s** (95% CI [+0.64, +0.75]), but
  that splits into **+1.29 s** (95% CI [+1.23, +1.36]) in the 537 races with a safety car
  and **exactly 0.00 s** in the 463 clean races. The free-recharge-under-safety-car rule
  is the whole effect.

- **An earlier apparent clean-race benefit was an artifact of free starting charge.**
  `data/b0_sweep.csv` shows the clean-race delta is exactly `b0 x 0.4` s for every
  starting charge `b0` — deploy and harvest are exact inverses, so any clean-race gain is
  just the energy the car was handed at lap 1. Setting `b0 = 0` isolates the rule itself.

- **The stochastic policy delays the first stop** relative to the deterministic optimum,
  gambling on a cheaper safety-car pit stop.

- **Adaptivity and the energy layer are worth about +2.46 s combined** against a fixed-lap,
  no-battery baseline. That decomposes exactly into **+1.77 s** from adaptive pit timing
  and **+0.69 s** from the 2026 energy layer, since the two effects are measured on the
  same 1,000 seeded races. Quoting the +2.46 s figure as the value of adaptivity alone
  would double-count the battery.

## License

MIT — see [LICENSE](LICENSE).
