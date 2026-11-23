"""Re-run the three experiments of the dissertation with the corrected model.

For every configuration, ``N_INSTANCES`` random instances are generated
(family seats and family bags are random). On each instance:

* the MIP chooses which seat each ordinary passenger gets, by number of bags;
* "random allocation" keeps the same Steffen boarding order but assigns
  bags to seats at random (200 draws) -- this isolates what the MIP adds;
* "random boarding" uses random seats and a random boarding order (200 draws),
  the usual baseline in the boarding literature.

All three are timed with the same simulation rules.

Usage:
    python run_experiments.py           # full run (several minutes)
    python run_experiments.py --fast    # 2 instances per configuration
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import numpy as np
import pandas as pd

from boarding import scenarios
from boarding.aircraft import ordinary_boarding_order
from boarding.evaluate import N_ROWS, evaluate_instance, random_allocation
from boarding.simulate import simulate

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"

SHARE_TWO_BAGS = [0.2, 0.4, 0.6, 0.8, 1.0]


def run_config(name, params, make, n_instances, seed0):
    rows = []
    for k in range(n_instances):
        rng = random.Random(seed0 + k)
        family, counts = make(rng)
        res = evaluate_instance(family, counts, rng)
        res.pop("mip_allocation")
        rows.append({"experiment": name, **params, "instance": k, **res})
    return rows


def experiment_1(n):
    rows = []
    for i, fam in enumerate([0.2, 0.4, 0.6]):
        for j, two in enumerate(SHARE_TWO_BAGS):
            make = lambda rng, fam=fam, two=two: scenarios.random_families(fam, two, rng)
            rows += run_config("1_bags", {"family_share": fam, "share_two_bags": two}, make, n, 1000 * i + 100 * j)
    return rows


def experiment_2(n):
    rows = []
    for j, n_window in enumerate([9, 19, 28, 38]):
        make = lambda rng, w=n_window: scenarios.families_in_window_seats(w, 0.4, 0.4, rng)
        rows += run_config("2_window", {"family_share": 0.4, "family_in_window": n_window, "share_two_bags": 0.4}, make, n, 5000 + 100 * j)
    return rows


def experiment_3(n):
    rows = []
    for i, fam in enumerate([0.2, 0.4]):
        for j, pairs in enumerate([0.2, 0.4]):
            make = lambda rng, fam=fam, pairs=pairs: scenarios.family_groups(fam, pairs, 0.6, rng)
            g2, g3 = scenarios.group_sizes(int(fam * scenarios.N_SEATS), pairs)
            params = {"family_share": fam, "pairs": g2, "triples": g3, "share_two_bags": 0.6}
            rows += run_config("3_groups", params, make, n, 8000 + 1000 * i + 100 * j)
    return rows


def robustness(n_instances, n_draws, sigma=0.3):
    """Stochastic check: each passenger's walking, sitting and stowing times
    are multiplied by independent lognormal factors (mean 1, log-sd sigma).
    The MIP allocation (planned with average times) and random allocations
    are evaluated on the same random draws."""
    rows = []
    for k in range(n_instances):
        rng = random.Random(20_000 + k)
        family, counts = scenarios.random_families(0.2, 0.4, rng)
        res = evaluate_instance(family, counts, rng, n_random=1)
        order = ordinary_boarding_order(N_ROWS, set(family))
        nprng = np.random.default_rng(k)
        n = len(order)
        for d in range(n_draws):
            f = {key: nprng.lognormal(-sigma**2 / 2, sigma, n) for key in ("walk_factor", "sit_factor", "store_factor")}
            t_mip = simulate(res["mip_allocation"], family, **f).total_time
            t_rand = simulate(random_allocation(order, counts, rng), family, **f).total_time
            rows.append({"instance": k, "draw": d, "t_mip": t_mip, "t_random_allocation": t_rand})
    return pd.DataFrame(rows)


def summarise(df: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    g = df.groupby(keys, sort=False)
    out = g.agg(
        total_bags=("total_bags", "mean"),
        t_mip=("t_mip", "mean"),
        t_random_allocation=("t_random_allocation_mean", "mean"),
        t_random_boarding=("t_random_boarding_mean", "mean"),
        mip_optimal=("mip_status", lambda s: (s == "Optimal").mean()),
    ).reset_index()
    out["gain_vs_random_allocation"] = 1 - out["t_mip"] / out["t_random_allocation"]
    out["gain_vs_random_boarding"] = 1 - out["t_mip"] / out["t_random_boarding"]
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fast", action="store_true")
    args = parser.parse_args()
    n = 2 if args.fast else 10
    RESULTS.mkdir(exist_ok=True)

    raw = pd.DataFrame(experiment_1(n) + experiment_2(n) + experiment_3(n))
    tables = {
        "experiment_1": summarise(raw[raw.experiment == "1_bags"], ["family_share", "share_two_bags"]),
        "experiment_2": summarise(raw[raw.experiment == "2_window"], ["family_in_window"]),
        "experiment_3": summarise(raw[raw.experiment == "3_groups"], ["family_share", "pairs", "triples"]),
    }
    rob = robustness(n_instances=2 if args.fast else 10, n_draws=20 if args.fast else 200)
    rob_summary = {
        "t_mip_mean": rob.t_mip.mean(),
        "t_random_allocation_mean": rob.t_random_allocation.mean(),
        "gain": 1 - rob.t_mip.mean() / rob.t_random_allocation.mean(),
        "share_of_draws_mip_faster": (rob.t_mip < rob.t_random_allocation).mean(),
        "n_draws": len(rob),
    }

    for name, t in tables.items():
        print(f"\n{name}\n{t.round(3).to_string(index=False)}")
    print("\nrobustness", json.dumps(rob_summary, indent=2))
    print("\nMIP solved to optimality on", (raw.mip_status == "Optimal").mean() * 100, "% of instances;",
          "max solve time", round(raw.mip_seconds.max(), 1), "s")
    print("MIP beat every random allocation on", raw.mip_beats_all_random_allocations.mean() * 100, "% of instances")

    if args.fast:
        return
    raw.to_csv(RESULTS / "instances.csv", index=False)
    for name, t in tables.items():
        t.to_csv(RESULTS / f"{name}.csv", index=False)
    rob.to_csv(RESULTS / "robustness_draws.csv", index=False)
    (RESULTS / "robustness_summary.json").write_text(json.dumps(rob_summary, indent=2))


if __name__ == "__main__":
    main()
