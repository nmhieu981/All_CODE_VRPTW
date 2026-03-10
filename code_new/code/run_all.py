"""
Batch runner — run iNSSSO on ALL Solomon instances, save to CSV.
"""
import os
import sys
import time
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))

from core.problem import VRPTWInstance, find_solomon_instances
from core.solution import SolutionParser
from core.objectives import FitnessEvaluator
from algorithm.inssso import iNSSSO

DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "csv")
OUTPUT_EXCEL = os.path.join(os.path.dirname(__file__), "results", "all_results.xlsx")
TIME_LIMIT = 100  # seconds per instance


def main():
    os.makedirs(os.path.dirname(OUTPUT_EXCEL), exist_ok=True)
    paths = sorted(find_solomon_instances(DATA_DIR, "csv"))
    print(f"Found {len(paths)} instances. Time limit: {TIME_LIMIT}s each.\n")

    results = []
    
    for i, path in enumerate(paths):
        inst = VRPTWInstance.load(path)
        name = inst.name
        print(f"[{i+1}/{len(paths)}] {name} ...", end=" ", flush=True)

        t0 = time.time()
        algo = iNSSSO(
            instance=inst,
            n_sol=100,
            cw=0.99,
            cg=0.95,
            n_abs=0.2,
            t_run=TIME_LIMIT,
        )
        pareto, info = algo.run()
        runtime = time.time() - t0

        best = min(pareto, key=lambda s: s.objectives[0])
        dist = best.objectives[0]
        n_routes = len(best.routes)

        print(f"dist={dist:.2f}, routes={n_routes}, time={runtime:.1f}s")

        results.append({
            "Instance": name,
            "Routes": n_routes,
            "Distance": round(dist, 2),
            "Runtime(s)": round(runtime, 1)
        })

        # Save immediately to Excel after each instance
        df = pd.DataFrame(results)
        df.to_excel(OUTPUT_EXCEL, index=False)

    print(f"\n{'='*60}")
    print(f"  All results saved to: {OUTPUT_EXCEL}")
    print(f"{'='*60}")

    # Summary
    print(f"\n{'Instance':<12} {'Routes':>7} {'Distance':>10} {'Time(s)':>9}")
    print("-" * 40)
    for r in results:
        print(f"{r['Instance']:<12} {r['Routes']:>7} {r['Distance']:>10.2f} {r['Runtime(s)']:>9.1f}")


if __name__ == "__main__":
    main()
