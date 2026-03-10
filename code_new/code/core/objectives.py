"""
Objective Functions  (f1, f2, f3)
=================================
Section 4.4, Equations 15–17 of Lai et al., Applied Soft Computing 2025.

f1 — total travel distance          (minimize)
f2 — customer dissatisfaction       (minimize) — average waiting time
f3 — workload imbalance             (minimize)
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np

from core.problem import VRPTWInstance
from core.solution import Solution, SolutionParser

PENALTY = 1e4  # penalty per unserved customer


class FitnessEvaluator:
    """Evaluate the three objectives for a given solution."""

    def __init__(self, instance: VRPTWInstance, use_eq17: bool = True):
        """
        Parameters
        ----------
        instance : VRPTWInstance
        use_eq17 : bool
            If True, use Eq (17) for f3 (Tmax normalisation).
            If False, use Eq (5)  for f3 (|Tk − Tavg| style).
        """
        self.inst = instance
        self.parser = SolutionParser(instance)
        self.use_eq17 = use_eq17

    # ----- single evaluation ------------------------------------------------
    def evaluate(self, solution: Solution) -> Tuple[float, float, float]:
        """Return (f1, f2, f3) and cache on the solution object."""
        # Make sure routes are decoded & parsed
        if solution.routes is None:
            solution.decode()
        self.parser.parse(solution)

        penalty = solution.restcus * PENALTY
        routes = solution.routes or []

        # f1 — total distance (Eq 15)
        total_dist = 0.0
        # f2 — average waiting time (Eq 16)
        total_wait = 0.0
        n_served = 0
        # f3 — workload imbalance (Eq 17 or Eq 5)
        completion_times: List[float] = []

        for route in routes:
            dist, waits, comp = self.parser.route_details(route)
            total_dist += dist
            total_wait += sum(waits)
            n_served += len(route)
            completion_times.append(comp)

        f1 = total_dist + penalty

        # f2 = average waiting / n_customers + penalty
        n = self.inst.n_customers
        f2 = (total_wait / n if n > 0 else 0.0) + penalty

        # f3
        f3 = self._compute_f3(completion_times) + penalty

        solution.objectives = (f1, f2, f3)
        return (f1, f2, f3)

    # ----- batch evaluation -------------------------------------------------
    def evaluate_batch(self, solutions: List[Solution]) -> List[Tuple[float, float, float]]:
        return [self.evaluate(s) for s in solutions]

    # ----- f3 variants ------------------------------------------------------
    def _compute_f3(self, completion_times: List[float]) -> float:
        if not completion_times:
            return 0.0

        if self.use_eq17:
            return self._f3_eq17(completion_times)
        return self._f3_eq5(completion_times)

    @staticmethod
    def _f3_eq17(cts: List[float]) -> float:
        """
        Eq (17):  f3 = (1/|σ|) * Σ (Tmax − Tk) / Tmax
        σ = set of used vehicles
        """
        t_max = max(cts)
        if t_max == 0:
            return 0.0
        sigma = len(cts)
        return sum((t_max - tk) / t_max for tk in cts) / sigma

    @staticmethod
    def _f3_eq5(cts: List[float]) -> float:
        """
        Eq (5):  f3 = Σ |Tk − Tavg|
        """
        t_avg = np.mean(cts)
        return float(sum(abs(tk - t_avg) for tk in cts))
