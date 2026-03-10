"""
Experiment Runner
=================
Orchestrates multi-algorithm, multi-run experiments on Solomon benchmarks.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple, Type

import numpy as np
import pandas as pd

from core.problem import VRPTWInstance, find_solomon_instances
from core.solution import Solution
from benchmark.metrics import PerformanceMetrics
from algorithm.inssso import iNSSSO
from algorithm.nssso import NSSSO
from comparison.mopso import MOPSO
from comparison.nsga2 import NSGA2
from comparison.moead import MOEAD
from comparison.spea2 import SPEA2

logger = logging.getLogger(__name__)


# Registry of algorithm classes
ALGORITHMS: Dict[str, Type] = {
    "iNSSSO": iNSSSO,
    "NSSSO": NSSSO,
    "MOPSO": MOPSO,
    "NSGA-II": NSGA2,
    "MOEA/D": MOEAD,
    "SPEA2": SPEA2,
}


class ExperimentRunner:
    """Run comparative experiments on Solomon benchmark instances."""

    def __init__(
        self,
        data_dir: str,
        results_dir: str = "results",
        n_runs: int = 15,
        time_limit: float = 60.0,
        n_sol: int = 100,
        fmt: str = "csv",
    ):
        self.data_dir = data_dir
        self.results_dir = results_dir
        self.n_runs = n_runs
        self.time_limit = time_limit
        self.n_sol = n_sol
        self.fmt = fmt
        self.metrics = PerformanceMetrics()

        os.makedirs(results_dir, exist_ok=True)

    # ----- run one algorithm on one instance --------------------------------
    def run_single_algorithm(
        self,
        algo_name: str,
        instance: VRPTWInstance,
        n_runs: Optional[int] = None,
    ) -> Dict[str, Any]:
        n_runs = n_runs or self.n_runs
        algo_cls = ALGORITHMS[algo_name]

        run_results: List[Dict[str, float]] = []
        all_pf_objs: List[np.ndarray] = []
        convergences: List[List[Tuple[float, float]]] = []

        for run in range(n_runs):
            logger.info("  %s run %d/%d on %s",
                         algo_name, run + 1, n_runs, instance.name)

            kwargs: Dict[str, Any] = {
                "instance": instance,
                "n_sol": self.n_sol,
                "t_run": self.time_limit,
            }
            # NSSSO: no greedy init, no ABS
            if algo_name == "NSSSO":
                pass  # defaults
            # Comparison algos: greedy init, no ABS
            elif algo_name in ("MOPSO", "NSGA-II", "MOEA/D", "SPEA2"):
                kwargs["use_greedy_init"] = True

            algo = algo_cls(**kwargs)
            pareto, info = algo.run()

            pf_obj = np.array([s.objectives for s in pareto])
            all_pf_objs.append(pf_obj)
            convergences.append(info.get("convergence", []))

        # Estimate true Pareto from all runs of ALL algorithms
        # (will be replaced in compare mode with aggregate)
        all_combined = np.vstack(all_pf_objs) if all_pf_objs else np.empty((0, 3))
        p_true = self.metrics.estimate_true_pareto(all_combined)

        # Compute metrics per run
        for pf_obj in all_pf_objs:
            m = self.metrics.compute_all(pf_obj, p_true)
            run_results.append(m)

        agg = self.metrics.aggregate(run_results)
        return {
            "algorithm": algo_name,
            "instance": instance.name,
            "metrics": agg,
            "all_pf": all_pf_objs,
            "convergences": convergences,
        }

    # ----- compare all algorithms on one instance ---------------------------
    def run_comparison(self, instance: VRPTWInstance) -> pd.DataFrame:
        """Compare 6 algorithms on a single instance."""
        algos = ["MOPSO", "NSGA-II", "MOEA/D", "SPEA2", "NSSSO", "iNSSSO"]
        all_solutions: List[np.ndarray] = []
        algo_results: Dict[str, Dict] = {}

        # First pass: collect all PF solutions
        for name in algos:
            result = self.run_single_algorithm(name, instance)
            algo_results[name] = result
            for pf in result["all_pf"]:
                if len(pf) > 0:
                    all_solutions.append(pf)

        # True Pareto from all
        combined = np.vstack(all_solutions) if all_solutions else np.empty((0, 3))
        p_true = self.metrics.estimate_true_pareto(combined)

        # Re-compute metrics with shared p_true
        rows = []
        for name in algos:
            run_metrics = []
            for pf_obj in algo_results[name]["all_pf"]:
                m = self.metrics.compute_all(pf_obj, p_true)
                run_metrics.append(m)
            agg = self.metrics.aggregate(run_metrics)
            row = {"Algorithm": name, "Instance": instance.name}
            for metric, (mean, std) in agg.items():
                row[f"{metric}_mean"] = mean
                row[f"{metric}_std"] = std
            rows.append(row)

        df = pd.DataFrame(rows)
        csv_path = os.path.join(self.results_dir, f"comparison_{instance.name}.csv")
        df.to_csv(csv_path, index=False)
        logger.info("Comparison saved to %s", csv_path)
        return df

    # ----- full Solomon benchmark run ---------------------------------------
    def full_solomon_benchmark(self) -> pd.DataFrame:
        """Run comparison on all 56 instances."""
        paths = find_solomon_instances(self.data_dir, self.fmt)
        all_dfs: List[pd.DataFrame] = []

        for path in paths:
            inst = VRPTWInstance.load(path)
            logger.info("=== Instance: %s ===", inst.name)
            df = self.run_comparison(inst)
            all_dfs.append(df)

        if all_dfs:
            result = pd.concat(all_dfs, ignore_index=True)
            result.to_csv(
                os.path.join(self.results_dir, "full_benchmark.csv"), index=False
            )
            return result
        return pd.DataFrame()
