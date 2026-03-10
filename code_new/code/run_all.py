"""
Batch runner — run iNSSSO on ALL Solomon instances, save to Excel.
Computes all 7 performance metrics from Section 12:
  Pareto metrics:      Cov, IGD, HV
  Preference metrics:  R-HV, Best_ASF, ROI_Count
  Auxiliary:           Nnds
"""
import os
import sys
import time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))

from core.problem import VRPTWInstance, find_solomon_instances
from core.solution import SolutionParser
from core.objectives import FitnessEvaluator
from core.preference import UserPreference
from algorithm.inssso import iNSSSO
from benchmark.metrics import PerformanceMetrics

DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "csv")
OUTPUT_EXCEL = os.path.join(os.path.dirname(__file__), "results", "all_results.xlsx")
TIME_LIMIT = 100  # seconds per instance
N_RUNS = 1        # runs per instance (set >1 for statistical analysis)


def main():
    os.makedirs(os.path.dirname(OUTPUT_EXCEL), exist_ok=True)
    paths = sorted(find_solomon_instances(DATA_DIR, "csv"))
    print(f"Found {len(paths)} instances. Time limit: {TIME_LIMIT}s each.")
    print(f"Runs per instance: {N_RUNS}\n")

    metrics_calc = PerformanceMetrics()
    results = []

    # ── Phase 1: Run algorithm on all instances ──
    # Store all pareto fronts for estimating true PF later
    all_pareto_data = {}  # instance_name -> list of (pareto_solutions, pref, info, runtime)

    for i, path in enumerate(paths):
        inst = VRPTWInstance.load(path)
        name = inst.name
        print(f"[{i+1}/{len(paths)}] {name}", flush=True)

        run_data = []
        for run_id in range(N_RUNS):
            if N_RUNS > 1:
                print(f"  Run {run_id+1}/{N_RUNS} ...", end=" ", flush=True)
            else:
                print(f"  Running ...", end=" ", flush=True)

            t0 = time.time()
            # Create iNSSSO with default preference (auto-calibrated)
            pref = UserPreference(
                g=np.array([800.0, 0.0, 0.1]),
                w=np.array([0.5, 0.3, 0.2]),
                delta=0.1,
            )
            algo = iNSSSO(
                instance=inst,
                n_sol=100,
                cw=0.99,
                cg=0.95,
                n_abs=0.2,
                t_run=TIME_LIMIT,
                preference=pref,
            )
            pareto, info = algo.run()
            runtime = time.time() - t0

            # Use the auto-calibrated preference from the algorithm
            calibrated_pref = algo.pref

            best = min(pareto, key=lambda s: s.objectives[0])
            dist = best.objectives[0]
            n_routes = len(best.routes)
            print(f"dist={dist:.2f}, routes={n_routes}, PF={len(pareto)}, "
                  f"gen={info['generations']}, time={runtime:.1f}s")

            run_data.append((pareto, calibrated_pref, info, runtime))

        all_pareto_data[name] = run_data

    # ── Phase 2: Estimate true Pareto front per instance ──
    print(f"\n{'='*60}")
    print("  Computing metrics ...")
    print(f"{'='*60}\n")

    for name, run_data in all_pareto_data.items():
        # Collect all solutions across runs for this instance
        all_objs_for_instance = []
        for pareto, _, _, _ in run_data:
            for s in pareto:
                if s.objectives is not None:
                    all_objs_for_instance.append(s.objectives)

        if not all_objs_for_instance:
            continue

        all_objs_array = np.array(all_objs_for_instance)
        p_true = metrics_calc.estimate_true_pareto(all_objs_array)

        # Compute metrics for each run
        for run_id, (pareto, pref, info, runtime) in enumerate(run_data):
            p_approx = np.array([s.objectives for s in pareto
                                 if s.objectives is not None])
            if len(p_approx) == 0:
                continue

            # Compute all 7 metrics
            m = metrics_calc.compute_all(p_approx, p_true, pref=pref)

            # Best solution (by distance)
            best = min(pareto, key=lambda s: s.objectives[0])
            dist = best.objectives[0]
            wait = best.objectives[1]
            imbalance = best.objectives[2]
            n_routes = len(best.routes)

            # Best solution by ASF (preference-closest)
            best_pref = min(pareto, key=lambda s: pref.asf(s.objectives)) if pref else best
            pref_dist = best_pref.objectives[0]
            pref_wait = best_pref.objectives[1]
            pref_imbal = best_pref.objectives[2]
            pref_routes = len(best_pref.routes)

            row = {
                "Instance": name,
                "Run": run_id + 1 if N_RUNS > 1 else None,
                # ── Best solution (by f1) ──
                "Routes": n_routes,
                "Distance (f1)": round(dist, 2),
                "Waiting (f2)": round(wait, 4),
                "Imbalance (f3)": round(imbalance, 6),
                # ── Best solution (by ASF) ──
                "ASF_Routes": pref_routes,
                "ASF_Distance": round(pref_dist, 2),
                "ASF_Waiting": round(pref_wait, 4),
                "ASF_Imbalance": round(pref_imbal, 6),
                # ── Pareto Metrics ──
                "Cov": round(m["Cov"], 4),
                "IGD": round(m["IGD"], 6),
                "HV": round(m["HV"], 6),
                # ── Preference Metrics ──
                "R-HV": round(m.get("R-HV", 0.0), 6),
                "Best_ASF": round(m.get("Best_ASF", float("inf")), 6),
                "ROI_Count": int(m.get("ROI_Count", 0)),
                # ── Auxiliary ──
                "Nnds": int(m["Nnds"]),
                "PF_Size": len(pareto),
                # ── Run Info ──
                "Generations": info["generations"],
                "Runtime(s)": round(runtime, 1),
            }

            # Remove Run column if single run
            if N_RUNS == 1:
                del row["Run"]

            results.append(row)

    # ── Save to Excel ──
    df = pd.DataFrame(results)

    # Format and save with multiple sheets
    with pd.ExcelWriter(OUTPUT_EXCEL, engine="openpyxl") as writer:
        # Main results sheet
        df.to_excel(writer, sheet_name="Results", index=False)

        # Summary sheet (mean ± std if multiple runs)
        if N_RUNS > 1:
            metric_cols = ["Routes", "Distance (f1)", "Waiting (f2)", "Imbalance (f3)",
                           "Cov", "IGD", "HV", "R-HV", "Best_ASF", "ROI_Count",
                           "Nnds", "PF_Size", "Generations", "Runtime(s)"]
            summary_rows = []
            for name in df["Instance"].unique():
                inst_df = df[df["Instance"] == name]
                row = {"Instance": name}
                for col in metric_cols:
                    if col in inst_df.columns:
                        mean_val = inst_df[col].mean()
                        std_val = inst_df[col].std()
                        row[f"{col}_mean"] = round(mean_val, 4)
                        row[f"{col}_std"] = round(std_val, 4)
                summary_rows.append(row)
            summary_df = pd.DataFrame(summary_rows)
            summary_df.to_excel(writer, sheet_name="Summary", index=False)

        # Metrics description sheet
        desc_data = [
            ["Metric", "Full Name", "Type", "Direction", "Description"],
            ["Cov", "Coverage", "Pareto", "Higher=Better",
             "% of true PF dominated by found PF → convergence"],
            ["IGD", "Inverted Generational Distance", "Pareto", "Lower=Better",
             "Avg distance from true PF to found PF → convergence + diversity"],
            ["HV", "Hypervolume", "Pareto", "Higher=Better",
             "Volume dominated under reference point → convergence + diversity + spread"],
            ["R-HV", "Restricted Hypervolume", "Preference", "Higher=Better",
             "HV computed only within ROI → preference guidance effectiveness"],
            ["Best_ASF", "Best Achievement Scalarizing Function", "Preference", "Lower=Better",
             "Closest solution to reference point g → preference satisfaction"],
            ["ROI_Count", "ROI Solution Count", "Preference", "Higher=Better",
             "Number of solutions within Region of Interest → preference density"],
            ["Nnds", "Non-dominated Set Size", "Auxiliary", "Higher=Better",
             "Number of non-dominated solutions → PF cardinality"],
        ]
        desc_df = pd.DataFrame(desc_data[1:], columns=desc_data[0])
        desc_df.to_excel(writer, sheet_name="Metrics Guide", index=False)

    print(f"\n{'='*60}")
    print(f"  All results saved to: {OUTPUT_EXCEL}")
    print(f"  Sheets: Results" + (", Summary" if N_RUNS > 1 else "") + ", Metrics Guide")
    print(f"{'='*60}")

    # Console summary table
    print(f"\n{'Instance':<12} {'Rts':>4} {'Distance':>10} {'HV':>8} "
          f"{'IGD':>8} {'R-HV':>8} {'ASF':>8} {'ROI':>4} {'Nnds':>5}")
    print("-" * 75)
    for r in results:
        print(f"{r['Instance']:<12} {r['Routes']:>4} {r['Distance (f1)']:>10.2f} "
              f"{r['HV']:>8.4f} {r['IGD']:>8.4f} {r['R-HV']:>8.4f} "
              f"{r['Best_ASF']:>8.4f} {r.get('ROI_Count', 0):>4} {r['Nnds']:>5}")


if __name__ == "__main__":
    main()
