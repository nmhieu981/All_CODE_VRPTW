"""
MOEA/D — Multi-Objective Evolutionary Algorithm based on Decomposition
======================================================================
Tchebycheff decomposition approach for MO-VRPTW.
"""

from __future__ import annotations

import logging
import time
from typing import Dict, List, Tuple

import numpy as np

from core.problem import VRPTWInstance
from core.solution import Solution, SolutionParser
from core.objectives import FitnessEvaluator
from algorithm.crowding import assign_rank_and_crowding
from algorithm.init_heuristics import greedy_nearest_neighbour

logger = logging.getLogger(__name__)


def _generate_weight_vectors(n: int, m: int = 3) -> np.ndarray:
    """Generate uniformly distributed weight vectors for *m* objectives."""
    if m == 3:
        weights = []
        for i in range(n):
            for j in range(n - i):
                k = n - 1 - i - j
                weights.append([i / (n - 1), j / (n - 1), k / (n - 1)])
                if len(weights) >= n:
                    return np.array(weights[:n])
        return np.array(weights[:n])
    # Fallback: random Dirichlet
    return np.random.dirichlet(np.ones(m), n)


class MOEAD:
    """MOEA/D with Tchebycheff decomposition for MO-VRPTW."""

    def __init__(
        self,
        instance: VRPTWInstance,
        n_sol: int = 100,
        t_run: float = 60.0,
        n_neighbours: int = 20,
        mutation_rate: float = 0.1,
        use_greedy_init: bool = True,
    ):
        self.inst = instance
        self.n_sol = n_sol
        self.t_run = t_run
        self.T = min(n_neighbours, n_sol)
        self.mut_rate = mutation_rate
        self.use_greedy_init = use_greedy_init
        self.evaluator = FitnessEvaluator(instance)
        self.parser = SolutionParser(instance)
        self.convergence: List[Tuple[float, float]] = []

    def _tchebycheff(self, obj: np.ndarray, weight: np.ndarray,
                     z_star: np.ndarray) -> float:
        return float(np.max(weight * np.abs(obj - z_star) + 1e-10))

    def run(self) -> Tuple[List[Solution], Dict]:
        logger.info("MOEA/D starting on %s", self.inst.name)

        # Weight vectors & neighbourhood
        weights = _generate_weight_vectors(self.n_sol, 3)
        dists = np.linalg.norm(weights[:, None] - weights[None, :], axis=2)
        neighbourhoods = np.argsort(dists, axis=1)[:, :self.T]

        # Init population
        pop: List[Solution] = []
        if self.use_greedy_init:
            nn = greedy_nearest_neighbour(self.inst)
            x1 = Solution.from_routes(nn, self.inst)
            x1.decode(); self.parser.parse(x1)
            pop.append(x1)
            n_start = 1
        else:
            n_start = 0

        for _ in range(n_start, self.n_sol):
            s = Solution.random(self.inst)
            s.decode(); self.parser.parse(s)
            pop.append(s)

        self.evaluator.evaluate_batch(pop)

        # Ideal point
        obj_all = np.array([s.objectives for s in pop])
        z_star = obj_all.min(axis=0).copy()

        start = time.time()
        gen = 0

        while time.time() - start < self.t_run:
            elapsed = time.time() - start
            obj_all = np.array([s.objectives for s in pop])
            ranks, _ = assign_rank_and_crowding(obj_all)
            pf_idx = [i for i, r in enumerate(ranks) if r == 0]
            proxy = float(np.mean(obj_all[pf_idx, 0])) if pf_idx else float("inf")
            self.convergence.append((elapsed, proxy))

            for i in range(self.n_sol):
                # Select parents from neighbourhood
                nb = neighbourhoods[i]
                j, k = np.random.choice(nb, 2, replace=False)

                # Crossover
                nvar = pop[i].nvar
                mask = np.random.rand(nvar) < 0.5
                child_keys = np.where(mask, pop[j].keys, pop[k].keys)
                # Mutation
                m_mask = np.random.rand(nvar) < self.mut_rate
                child_keys[m_mask] = np.random.rand(m_mask.sum())

                child = Solution(keys=child_keys,
                                 n_customers=pop[i].n_customers,
                                 n_vehicles=pop[i].n_vehicles)
                child.decode(); self.parser.parse(child)
                self.evaluator.evaluate(child)

                # Update ideal point
                child_obj = np.array(child.objectives)
                z_star = np.minimum(z_star, child_obj)

                # Update neighbours
                for idx in nb:
                    cur_tch = self._tchebycheff(
                        np.array(pop[idx].objectives), weights[idx], z_star)
                    new_tch = self._tchebycheff(child_obj, weights[idx], z_star)
                    if new_tch < cur_tch:
                        pop[idx] = child.clone()

            gen += 1

        obj_all = np.array([s.objectives for s in pop])
        ranks, _ = assign_rank_and_crowding(obj_all)
        for i, s in enumerate(pop): s.rank = ranks[i]
        pareto = [s for s in pop if s.rank == 0]
        logger.info("MOEA/D done: %d gen, PF=%d", gen, len(pareto))
        return pareto, {"generations": gen, "runtime": time.time()-start,
                        "convergence": self.convergence}
