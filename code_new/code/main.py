#!/usr/bin/env python
"""
iNSSSO — Main Entry Point
==========================
CLI for running iNSSSO experiments on Solomon MO-VRPTW benchmarks.
Supports preference-based optimization with R-Dominance.

Usage
-----
    python main.py --mode single --instance C101 --time 10
    python main.py --mode compare --instance C101
    python main.py --mode full
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

import numpy as np
import yaml

from core.problem import VRPTWInstance, find_solomon_instances
from core.solution import SolutionParser
from core.objectives import FitnessEvaluator
from core.preference import UserPreference
from algorithm.inssso import iNSSSO
from algorithm.nssso import NSSSO
from benchmark.metrics import PerformanceMetrics
from benchmark.runner import ExperimentRunner
from visualization.pareto_plot import plot_pareto_2d
from visualization.convergence_plot import plot_convergence
from visualization.route_visualizer import plot_routes


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def load_config(config_path: str = "config/params.yaml") -> dict:
    config_abs = os.path.join(os.path.dirname(__file__), config_path)
    if os.path.exists(config_abs):
        with open(config_abs, "r") as f:
            return yaml.safe_load(f)
    return {}


def load_preference(config: dict) -> UserPreference | None:
    """Load UserPreference from config, or None if not configured."""
    pref_cfg = config.get("preference", {})
    if not pref_cfg:
        return None

    g = np.array(pref_cfg.get("reference_point", [828.0, 0.0, 0.12]))
    w = np.array(pref_cfg.get("weights", [0.5, 0.3, 0.2]))
    delta = pref_cfg.get("roi_delta", 0.1)

    return UserPreference(g=g, w=w, delta=delta)


def find_instance(data_dir: str, name: str, fmt: str = "csv") -> str:
    """Find the file path for a given instance name."""
    paths = find_solomon_instances(data_dir, fmt)
    for p in paths:
        base = os.path.splitext(os.path.basename(p))[0]
        if base.upper() == name.upper():
            return p
    raise FileNotFoundError(f"Instance '{name}' not found in {data_dir}")


# ===== Modes ================================================================

def mode_single(args, config):
    """Run iNSSSO on a single instance."""
    data_dir = os.path.join(os.path.dirname(__file__), config.get("experiment", {}).get("data_dir", "data/csv"))
    fmt = config.get("experiment", {}).get("data_format", "csv")

    path = find_instance(data_dir, args.instance, fmt)
    instance = VRPTWInstance.load(path)

    # Load preference
    pref = load_preference(config)

    print(f"\n{'='*60}")
    print(f"  Instance : {instance.name}")
    print(f"  Customers: {instance.n_customers}")
    print(f"  Vehicles : {instance.n_vehicles}")
    print(f"  Capacity : {instance.capacity}")
    print(f"  Time     : {args.time}s")
    if pref is not None:
        print(f"  Ref Point: g = {pref.g.tolist()}")
        print(f"  Weights  : w = {pref.w.tolist()}")
        print(f"  ROI Delta: delta = {pref.delta}")
    print(f"{'='*60}\n")

    algo_cfg = config.get("algorithm", {})
    algo = iNSSSO(
        instance=instance,
        n_sol=algo_cfg.get("n_sol", 200),
        cw=algo_cfg.get("cw", 0.99),
        cg=algo_cfg.get("cg", 0.95),
        n_abs=algo_cfg.get("n_abs", 0.2),
        t_run=args.time,
        archive_size=algo_cfg.get("archive_size", 200),
        epsilon=algo_cfg.get("epsilon", 0.01),
        ls_rate_rank0=algo_cfg.get("ls_rate_rank0", 0.15),
        mutation_rate=algo_cfg.get("mutation_rate", 0.05),
        preference=pref,
    )

    pareto, info = algo.run()

    print(f"\n{'='*60}")
    print(f"  Results")
    print(f"{'='*60}")
    print(f"  Generations : {info['generations']}")
    print(f"  Runtime     : {info['runtime']:.1f}s")
    print(f"  PF Size     : {len(pareto)}")

    # Show auto-calibrated reference point
    if pref is not None:
        print(f"  Auto-cal g  : [{pref.g[0]:.2f}, {pref.g[1]:.4f}, {pref.g[2]:.6f}]")

    if pareto:
        objs = np.array([s.objectives for s in pareto])
        metrics = PerformanceMetrics()
        hv = metrics.hypervolume(objs)
        nnds = metrics.nnds(objs)

        print(f"  HV          : {hv:.6f}")
        print(f"  Nnds        : {nnds}")

        # Preference-based metrics
        if pref is not None:
            r_hv = metrics.r_hypervolume(objs, pref)
            best_asf = metrics.best_asf(objs, pref)
            roi_n = metrics.roi_count(objs, pref)
            print(f"  R-HV        : {r_hv:.6f}")
            print(f"  Best ASF    : {best_asf:.6f}")
            print(f"  ROI Count   : {roi_n}/{len(pareto)}")

        best_sol = min(pareto, key=lambda s: s.objectives[0])
        print(f"  Best Dist   : {best_sol.objectives[0]:.2f}  ({len(best_sol.routes)} routes)")

        # Best by ASF
        if pref is not None:
            best_asf_sol = min(pareto, key=lambda s: pref.asf(s.objectives))
            print(f"  Best ASF Sol: f1={best_asf_sol.objectives[0]:.2f}  "
                  f"f2={best_asf_sol.objectives[1]:.4f}  "
                  f"f3={best_asf_sol.objectives[2]:.6f}  "
                  f"ASF={pref.asf(best_asf_sol.objectives):.6f}")

        print(f"\n  Pareto Front objectives (f1, f2, f3):")
        for i, s in enumerate(pareto[:10]):
            asf_str = ""
            if pref is not None:
                asf_str = f"  ASF={pref.asf(s.objectives):.4f}"
            print(f"    [{i+1}] f1={s.objectives[0]:.2f}  "
                  f"f2={s.objectives[1]:.4f}  f3={s.objectives[2]:.6f}  "
                  f"routes={len(s.routes)}  unserved={s.restcus}{asf_str}")
        if len(pareto) > 10:
            print(f"    ... and {len(pareto)-10} more")

        # Plot
        results_dir = config.get("experiment", {}).get("results_dir", "results")
        os.makedirs(results_dir, exist_ok=True)

        plot_pareto_2d({"iNSSSO": objs}, instance.name, save_dir=results_dir)
        print(f"\n  Pareto plot saved to {results_dir}/pareto_{instance.name}.png")

        # Plot best route
        best_sol = min(pareto, key=lambda s: s.objectives[0])
        plot_routes(best_sol, instance, save_dir=results_dir)
        print(f"  Route plot saved to {results_dir}/routes_{instance.name}.png")

        # Convergence
        conv_data = {"iNSSSO": [info["convergence"]]}
        plot_convergence(conv_data, instance.name, save_dir=results_dir)
        print(f"  Convergence plot saved to {results_dir}/convergence_{instance.name}.png")

    print(f"{'='*60}\n")


def mode_compare(args, config):
    """Compare 6 algorithms on a single instance."""
    data_dir = os.path.join(os.path.dirname(__file__), config.get("experiment", {}).get("data_dir", "data/csv"))
    fmt = config.get("experiment", {}).get("data_format", "csv")
    results_dir = config.get("experiment", {}).get("results_dir", "results")

    path = find_instance(data_dir, args.instance, fmt)
    instance = VRPTWInstance.load(path)
    print(f"\nComparing algorithms on {instance.name} ({args.runs} runs, {args.time}s each)...\n")

    runner = ExperimentRunner(
        data_dir=data_dir,
        results_dir=results_dir,
        n_runs=args.runs,
        time_limit=args.time,
        fmt=fmt,
    )
    df = runner.run_comparison(instance)
    print("\n" + df.to_string(index=False))
    print(f"\nResults saved to {results_dir}/comparison_{instance.name}.csv")


def mode_full(args, config):
    """Full Solomon benchmark run."""
    data_dir = os.path.join(os.path.dirname(__file__), config.get("experiment", {}).get("data_dir", "data/csv"))
    fmt = config.get("experiment", {}).get("data_format", "csv")
    results_dir = config.get("experiment", {}).get("results_dir", "results")

    print(f"\nFull Solomon benchmark ({args.runs} runs, {args.time}s each)...\n")

    runner = ExperimentRunner(
        data_dir=data_dir,
        results_dir=results_dir,
        n_runs=args.runs,
        time_limit=args.time,
        fmt=fmt,
    )
    df = runner.full_solomon_benchmark()
    print(f"\nBenchmark complete. Results saved to {results_dir}/full_benchmark.csv")
    print(f"Total rows: {len(df)}\n")


# ===== Main =================================================================

def main():
    setup_logging()
    config = load_config()

    parser = argparse.ArgumentParser(
        description="iNSSSO — MO-VRPTW Algorithm Suite",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--mode",
        choices=["single", "compare", "full"],
        default="single",
        help="Execution mode:\n"
             "  single  — run iNSSSO on one instance\n"
             "  compare — compare 6 algorithms on one instance\n"
             "  full    — full Solomon 56-instance benchmark",
    )
    parser.add_argument("--instance", default="C101",
                        help="Instance name (default: C101)")
    parser.add_argument("--time", type=int, default=60,
                        help="Time limit per run in seconds (default: 60)")
    parser.add_argument("--runs", type=int, default=15,
                        help="Number of independent runs (default: 15)")

    args = parser.parse_args()

    if args.mode == "single":
        mode_single(args, config)
    elif args.mode == "compare":
        mode_compare(args, config)
    elif args.mode == "full":
        mode_full(args, config)


if __name__ == "__main__":
    main()
