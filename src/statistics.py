"""
statistics.py -- uncertainty quantification for
"Modeling Optimal Race Strategy Under the 2026 Formula 1 Regulations"

Run from anywhere:   python src/statistics.py
Reads:  data/paired_races.csv, data/policy_races.csv,
        data/circuit_races.csv, data/clean_laps.csv, data/validation.csv
Writes: results/statistics_standalone.json, results/figure_forest.png

This is a standalone re-derivation of the paper's uncertainty estimates from the
committed CSVs, kept separate from the figures-and-numbers path in
master_analysis.ipynb (which writes results/statistics.json). The two agree on
the headline quantities but differ in one definition: the per-circuit intervals
below are computed over ALL races, whereas the notebook reports them over the
safety-car subset only. The outputs are deliberately written to different
filenames so neither overwrites the other.

Why intervals and not p-values, for the simulated quantities:
  Delta, the win rate and the per-circuit effects come out of a simulator whose
  sample size we choose. A p-value on those would only report how many races we
  elected to run, so we report bootstrap confidence intervals instead. The tyre
  regression and the model-vs-actual validation use observed data whose sample
  size is fixed by the season, so those get full inference.
"""

import json
import os
import numpy as np
import pandas as pd
from scipy import stats
import statsmodels.formula.api as smf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SEED, N_BOOT = 20260903, 10_000
rng = np.random.default_rng(SEED)

# Paths are resolved from this file, so the script runs from any directory.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
RESULTS = os.path.join(ROOT, "results")
os.makedirs(RESULTS, exist_ok=True)
R = {}


def dpath(name):
    return os.path.join(DATA, name)


# ---------------------------------------------------------------- helpers
def boot_mean_ci(x, alpha=0.05):
    x = np.asarray(x, float)
    idx = rng.integers(0, len(x), size=(N_BOOT, len(x)))
    m = x[idx].mean(axis=1)
    lo, hi = np.percentile(m, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(x.mean()), float(lo), float(hi)


def boot_diff_ci(a, b, alpha=0.05):
    a, b = np.asarray(a, float), np.asarray(b, float)
    ia = rng.integers(0, len(a), size=(N_BOOT, len(a)))
    ib = rng.integers(0, len(b), size=(N_BOOT, len(b)))
    d = a[ia].mean(axis=1) - b[ib].mean(axis=1)
    lo, hi = np.percentile(d, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(a.mean() - b.mean()), float(lo), float(hi)


def wilson_ci(k, n, z=1.96):
    p = k / n
    den = 1 + z**2 / n
    c = (p + z**2 / (2 * n)) / den
    h = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / den
    return float(p), float(c - h), float(c + h)


def has(p):
    return os.path.exists(p)


# ------------------------------------------------ 1. battery effect (Delta)
d = pd.read_csv(dpath("paired_races.csv"))
delta = d["delta"].to_numpy(float)

m, lo, hi = boot_mean_ci(delta)
R["delta_overall"] = {"mean": m, "ci": [lo, hi],
                      "sd": float(delta.std(ddof=1)),
                      "mc_se": float(delta.std(ddof=1) / np.sqrt(len(delta))),
                      "n": int(len(delta))}

sc = d.loc[d["had_sc"], "delta"].to_numpy(float)
gr = d.loc[~d["had_sc"], "delta"].to_numpy(float)
for key, arr in (("delta_safety_car", sc), ("delta_green", gr)):
    m, lo, hi = boot_mean_ci(arr)
    R[key] = {"mean": m, "ci": [lo, hi],
              "mc_se": float(arr.std(ddof=1) / np.sqrt(len(arr))),
              "n": int(len(arr))}

# The headline is that the benefit CONCENTRATES under safety cars. That is a
# claim about the gap between the subsets, so bootstrap the gap itself.
m, lo, hi = boot_diff_ci(sc, gr)
R["delta_sc_minus_green"] = {"mean": m, "ci": [lo, hi],
                             "excludes_zero": bool(lo > 0 or hi < 0)}

R["paired_cohens_d"] = float(delta.mean() / delta.std(ddof=1))

# Sanity check tied to the b0 finding: with b0=0 the clean-race subset should
# sit near 0, because deploy (-0.4) and harvest (+0.4) are exact inverses.
R["delta_green_near_zero"] = bool(abs(R["delta_green"]["mean"]) < 0.05)


# ------------------------------------------------ 2. adaptive vs fixed plan
if has(dpath("policy_races.csv")):
    p = pd.read_csv(dpath("policy_races.csv"))
    gap = (p["t_fixed"] - p["t_adaptive"]).to_numpy(float)
    m, lo, hi = boot_mean_ci(gap)
    R["adaptive_gain"] = {"mean": m, "ci": [lo, hi],
                          "mc_se": float(gap.std(ddof=1) / np.sqrt(len(gap)))}

    tol = 1e-6
    wins, ties = int((gap > tol).sum()), int((np.abs(gap) <= tol).sum())
    losses = int((gap < -tol).sum())
    prop, plo, phi = wilson_ci(wins + ties, len(gap))
    R["adaptive_record"] = {"wins": wins, "ties": ties, "losses": losses,
                            "win_or_tie_rate": prop, "wilson_ci": [plo, phi]}

    # A naive ceiling on the adaptive gain: P(SC) x the pit discount.
    # Reporting the realised value against this bound explains the mechanism.
    R["adaptive_naive_bound"] = 0.5417 * (26.4 - 12.0)


# ------------------------------------------------ 3. cross-circuit
if has(dpath("circuit_races.csv")):
    c = pd.read_csv(dpath("circuit_races.csv"))
    R["delta_by_circuit"] = {}
    for name, grp in c.groupby("circuit"):
        m, lo, hi = boot_mean_ci(grp["delta"].to_numpy(float))
        R["delta_by_circuit"][name] = {"mean": m, "ci": [lo, hi], "n": int(len(grp))}
    # No ANOVA: failing to reject is not evidence of equality, and n is ours.
    # Overlapping intervals make the point directly and honestly.


# --------------------------- 4. tyre regression -- REAL DATA, full inference
if has(dpath("clean_laps.csv")):
    laps = pd.read_csv(dpath("clean_laps.csv"))
    laps = laps.rename(columns={"LapTimeS": "lap_time", "TyreLife": "tyre_age",
                                "LapNumber": "lap_number", "Compound": "compound",
                                "Track": "circuit", "Stint": "stint",
                                "Driver": "driver"})
    laps["compound"] = laps["compound"].str.upper()
    laps = laps.dropna(subset=["lap_time", "tyre_age", "lap_number", "compound"])
    if {"driver", "stint", "circuit"} <= set(laps.columns):
        laps["stint_id"] = (laps["circuit"].astype(str) + "_" +
                            laps["driver"].astype(str) + "_" +
                            laps["stint"].astype(str))

    R["tyre_regression"] = {}
    for comp in ["SOFT", "MEDIUM", "HARD"]:
        sub = laps[laps["compound"] == comp]
        if len(sub) < 30:
            continue
        fit = smf.ols("lap_time ~ tyre_age + lap_number", data=sub)
        res = (fit.fit(cov_type="cluster", cov_kwds={"groups": sub["stint_id"]})
               if "stint_id" in sub.columns else fit.fit())
        ci = res.conf_int().loc["tyre_age"]
        R["tyre_regression"][comp] = {
            "base": float(res.params["Intercept"]),
            "wear_rate": float(res.params["tyre_age"]),
            "wear_se": float(res.bse["tyre_age"]),
            "wear_ci": [float(ci.iloc[0]), float(ci.iloc[1])],
            "fuel_effect": float(res.params["lap_number"]),
            "r_squared": float(res.rsquared),
            "n_laps": int(len(sub)),
            "n_circuits": int(sub["circuit"].nunique()) if "circuit" in sub else None,
        }

    tr = R["tyre_regression"]
    if {"MEDIUM", "HARD"} <= set(tr):
        a, b = tr["MEDIUM"]["wear_ci"], tr["HARD"]["wear_ci"]
        R["medium_hard_ci_overlap"] = bool(not (a[1] < b[0] or b[1] < a[0]))

    # Compound base pace WITH circuit fixed effects. Without these the raw
    # intercepts are not comparable: SOFT is fitted on 2 circuits, MEDIUM on 7,
    # so the plain intercept gap is mostly track pace, not compound pace.
    if "circuit" in laps.columns and laps["circuit"].nunique() > 1:
        fe = smf.ols("lap_time ~ C(compound) + tyre_age + lap_number + C(circuit)",
                     data=laps).fit()
        pm = [k for k in fe.params.index if "compound" in k and "MEDIUM" in k]
        if pm:
            R["base_pace_medium_minus_soft_fe"] = float(fe.params[pm[0]])
            R["base_pace_fe_note"] = "compound dummies with circuit fixed effects"

    # Corrected undercut threshold. At the stop the rival is on an OLD SOFT,
    # not an old medium, so use the soft wear rate; then subtract the pace
    # penalty of a fresh medium relative to a fresh soft.
    if "SOFT" in tr and "base_pace_medium_minus_soft_fe" in R:
        AGE = 22          # rival tyre age at the model's optimal stop
        gross = tr["SOFT"]["wear_rate"] * AGE
        R["undercut"] = {"rival_age": AGE, "gross_gain": float(gross),
                         "compound_penalty": R["base_pace_medium_minus_soft_fe"],
                         "net_threshold": float(gross - R["base_pace_medium_minus_soft_fe"])}


# ---------------------- 5. model-vs-actual validation -- REAL DATA, inference
if has(dpath("validation.csv")):
    v = pd.read_csv(dpath("validation.csv"))
    err = (v["model_lap"] - v["actual_lap"]).to_numpy(float)
    e = {"n_races": int(len(err)), "mean_error": float(err.mean()),
         "mae": float(np.abs(err).mean()),
         "sd": float(err.std(ddof=1)) if len(err) > 1 else None,
         "min": float(err.min()), "max": float(err.max())}
    if len(err) >= 6:
        s, pv = stats.wilcoxon(err)
        e["wilcoxon_stat"], e["wilcoxon_p"] = float(s), float(pv)
    else:
        e["note"] = ("Fewer than 6 races: a signed-rank test is not meaningful. "
                     "Solve the remaining 2026 high-speed circuits first.")
    R["validation"] = e


# ------------------------------------------------------------------ figure
labels, means, los, his = [], [], [], []
for key, lab in [("delta_green", "Clean races"),
                 ("delta_safety_car", "Safety-car races"),
                 ("delta_overall", "All races")]:
    if key in R:
        labels.append(lab)
        means.append(R[key]["mean"])
        los.append(R[key]["ci"][0])
        his.append(R[key]["ci"][1])

fig, ax = plt.subplots(figsize=(6.5, 2.6))
y = np.arange(len(labels))
ax.errorbar(means, y,
            xerr=[np.array(means) - np.array(los), np.array(his) - np.array(means)],
            fmt="o", color="#1f1f1f", capsize=4, markersize=5, linewidth=1.4)
ax.axvline(0, color="#999999", ls="--", lw=1)
ax.set_yticks(y)
ax.set_yticklabels(labels)
ax.set_xlabel("Time saved by the 2026 battery rule, $\\Delta$ (s per race)")
ax.set_ylim(-0.6, len(labels) - 0.4)
ax.spines[["top", "right"]].set_visible(False)
ax.grid(axis="x", alpha=0.25)
fig.tight_layout()
fig.savefig(os.path.join(RESULTS, "figure_forest.png"), dpi=300, bbox_inches="tight")

with open(os.path.join(RESULTS, "statistics_standalone.json"), "w") as f:
    json.dump(R, f, indent=2)

# ------------------------------------------------------------ paste-ready
print("\n=== paste into Results ===")
o, s_, g = R["delta_overall"], R["delta_safety_car"], R["delta_green"]
f_ = lambda x: f"{x['mean']:+.2f} s (95% CI [{x['ci'][0]:+.2f}, {x['ci'][1]:+.2f}])"
print(f"overall     {f_(o)}, MC SE = {o['mc_se']:.3f} s, n = {o['n']}")
print(f"safety car  {f_(s_)}, n = {s_['n']}")
print(f"clean       {f_(g)}, n = {g['n']}")
print(f"SC - clean  {f_(R['delta_sc_minus_green'])}")
if "adaptive_record" in R:
    a, rec = R["adaptive_gain"], R["adaptive_record"]
    print(f"adaptive    {f_(a)}; {rec['wins']}W/{rec['ties']}T/{rec['losses']}L, "
          f"win-or-tie {rec['win_or_tie_rate']:.1%} "
          f"[{rec['wilson_ci'][0]:.1%}, {rec['wilson_ci'][1]:.1%}]")
if "delta_by_circuit" in R:
    for k_, v_ in R["delta_by_circuit"].items():
        print(f"{k_:12s} {f_(v_)}")
if "tyre_regression" in R:
    for c_, r_ in R["tyre_regression"].items():
        print(f"{c_:7s} wear {r_['wear_rate']:.4f} "
              f"[{r_['wear_ci'][0]:.4f}, {r_['wear_ci'][1]:.4f}] "
              f"R2={r_['r_squared']:.3f} n={r_['n_laps']}")
    if R.get("medium_hard_ci_overlap"):
        print("  -> MEDIUM and HARD wear intervals OVERLAP: the ordering is not "
              "distinguishable from sampling variation. Say this in the paper.")
if "undercut" in R:
    u = R["undercut"]
    print(f"undercut    net {u['net_threshold']:+.2f} s "
          f"(gross {u['gross_gain']:.2f} - compound {u['compound_penalty']:.2f})")