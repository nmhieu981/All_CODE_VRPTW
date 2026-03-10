"""
Base NSSSO  (Non-dominated Sorting Simplified Swarm Optimization)
=================================================================
Base variant — no LKH initialisation, no ABS local search.
"""

from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional, Tuple

import numpy as np

from core.problem import VRPTWInstance
from core.solution import Solution, SolutionParser
from core.objectives import FitnessEvaluator
from algorithm.nondominated import fast_nondominated_sort
from algorithm.crowding import (
    assign_rank_and_crowding,
    crowding_distance,
    select_best,
    select_gbest,
)

logger = logging.getLogger(__name__)


class NSSSO:
    """
    Base NSSSO — SSO update rule (Eq 2) with nondominated sorting.
    No LKH init, no ABS.
    """

    def __init__(
        self,
        instance: VRPTWInstance,
        n_sol: int = 100,
        cw: float = 0.99,
        cg: float = 0.95,
        t_run: float = 60.0,
    ):
        self.inst = instance
        self.n_sol = n_sol
        self.cw = cw
        self.cg = cg
        self.t_run = t_run
        self.evaluator = FitnessEvaluator(instance)
        self.parser = SolutionParser(instance)

        # State
        self.population: List[Solution] = []
        self.convergence: List[Tuple[float, float]] = []  # (time, igd_approx)

    # ----- initialisation ---------------------------------------------------
    def initialize_population(self) -> List[Solution]:
        """Random initialisation for base NSSSO."""
        pop = [Solution.random(self.inst) for _ in range(self.n_sol)]
        for sol in pop:
            sol.decode()
            self.parser.parse(sol)
        return pop

    # ----- SSO update (Eq 2) ------------------------------------------------
    def update_solution(self, xi: Solution, gbest: Solution) -> Solution:
        """
        Eq (2) — simplified update rule (pBest removed), vectorised.
        """
        nvar = xi.nvar
        rho = np.random.rand(nvar)
        random_keys = np.random.rand(nvar)
        new_keys = np.where(
            rho <= self.cg,
            gbest.keys,
            np.where(rho <= self.cw, xi.keys, random_keys),
        )
        return Solution(
            keys=new_keys,
            n_customers=xi.n_customers,
            n_vehicles=xi.n_vehicles,
        )

    # ----- main loop --------------------------------------------------------
    def run(self) -> Tuple[List[Solution], Dict]:
        """
        Main evolution loop.

        Returns
        -------
        pareto_front : list[Solution]
        info : dict with convergence history, runtime, etc.
        """
        logger.info("NSSSO starting on %s  (nSol=%d, tRun=%.0fs)",
                     self.inst.name, self.n_sol, self.t_run)

        # 1. Initialise
        self.population = self.initialize_population()
        self.evaluator.evaluate_batch(self.population)

        start = time.time()
        generation = 0

        while True:
            elapsed = time.time() - start
            if elapsed >= self.t_run:
                break

            # Objectives matrix
            obj_matrix = np.array([s.objectives for s in self.population])
            ranks, cds = assign_rank_and_crowding(obj_matrix)
            for i, sol in enumerate(self.population):
                sol.rank = ranks[i]
                sol.crowding_distance = cds[i]

            # Pareto front indices (rank 0)
            pf_indices = [i for i in range(len(self.population)) if ranks[i] == 0]
            pf_cds = cds[pf_indices]

            # Record convergence (mean of pf objectives as proxy)
            pf_obj = obj_matrix[pf_indices]
            igd_proxy = float(np.mean(pf_obj[:, 0])) if len(pf_indices) > 0 else float("inf")
            self.convergence.append((elapsed, igd_proxy))

            # Generate offspring
            offspring: List[Solution] = []
            for i in range(self.n_sol):
                gb_idx = select_gbest(pf_indices, pf_cds)
                gbest = self.population[gb_idx]
                yi = self.update_solution(self.population[i], gbest)
                yi.decode()
                self.parser.parse(yi)
                self.evaluator.evaluate(yi)
                offspring.append(yi)

            # Combine + select
            merged = self.population + offspring
            merged_obj = np.array([s.objectives for s in merged])
            best_indices = select_best(merged_obj, self.n_sol)
            self.population = [merged[i] for i in best_indices]

            generation += 1

        # Final ranking
        obj_matrix = np.array([s.objectives for s in self.population])
        ranks, cds = assign_rank_and_crowding(obj_matrix)
        for i, sol in enumerate(self.population):
            sol.rank = ranks[i]
            sol.crowding_distance = cds[i]

        pareto = [s for s in self.population if s.rank == 0]
        elapsed = time.time() - start
        logger.info("NSSSO finished: %d generations, %.1fs, PF size=%d",
                     generation, elapsed, len(pareto))

        return pareto, {
            "generations": generation,
            "runtime": elapsed,
            "convergence": self.convergence,
        }
