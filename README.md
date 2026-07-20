# Optimal Race Strategy Under the 2026 Formula One Regulations

How do the 2026 Formula One regulations influence optimal race strategy on high-speed
circuits? This project builds an empirically calibrated, stochastic model of an F1 race
and uses it to derive optimal pit-stop, tyre, and energy-deployment strategies — with a
particular focus on the new 2026 electrical-deployment and safety-car recharging rules.

## Approach

The model is built up in layers, each in its own notebook:

1. **Empirical calibration** — tyre-degradation rates, pit-stop time loss, and safety-car
   frequencies are estimated from real 2025 telemetry (via the FastF1 / OpenF1 APIs).
2. **Deterministic baseline** — dynamic programming finds the optimal fixed pit strategy
   assuming no safety cars.
3. **Stochastic dynamic programming (SDP)** — a 2-state geometric-duration Markov chain
   models random safety cars, and backward induction yields an adaptive policy.
4. **2026 battery layer** — battery state and energy-management actions (deploy / hold /
   harvest, plus free recharging under safety cars) are added to the state space.
5. **Game theory** — a Stackelberg model of the undercut between two drivers.
6. **Validation** — model predictions are checked against actual 2026 race data.

## Repository layout

```
src/
  pitstops.ipynb          Empirical calibration from 2025 data -> parameters.json
  model0DP.ipynb          Deterministic baseline (dynamic programming)
  markovSDP.ipynb         Stochastic DP with the safety-car Markov chain
  batteryimplement.ipynb  2026 battery / energy-deployment layer
  gametheory.ipynb        Undercut game (Stackelberg)
  highspeedTracks.ipynb   Full model across multiple high-speed circuits
  validationtesting.ipynb Validation against 2026 results
  parameters.json         Calibrated model parameters
images/
  visualizations.ipynb    Figure generation (Markov chain, transition matrix, results)
  *.png                   Exported figures
```

## Getting started

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
jupyter notebook
```

Run `src/pitstops.ipynb` first to (re)generate `parameters.json`, then the modelling
notebooks in the order listed above. The FastF1 API cache is stored in `src/f1_cache/`
and is regenerated automatically on first run (it is git-ignored).

## Key results

- The stochastic policy **delays the first stop** relative to the deterministic optimum,
  gambling on a cheaper safety-car pit stop.
- Across 1,000 randomized races the adaptive policy beats or ties a fixed plan **~72%** of
  the time, averaging **~1.75 s/race**.
- The 2026 free-recharge-under-safety-car rule measurably raises the value of the battery
  layer on high-speed circuits.
