"""
NSGA-II — Non-dominated Sorting Genetic Algorithm II
=====================================================
Adapted for MO-VRPTW with random-key encoding.
"""

from __future__ import annotations

import logging
import time
from typing import Dict, List, Tuple

import numpy as np

from core.problem import VRPTWInstance
from core.solution import Solution, SolutionParser
from core.objectives import FitnessEvaluator
from algorithm.crowding import assign_rank_and_crowding, select_best
from algorithm.init_heuristics import greedy_nearest_neighbour

logger = logging.getLogger(__name__)


class NSGA2:
    """NSGA-II for MO-VRPTW."""

    def __init__(
        self,
        instance: VRPTWInstance,
        n_sol: int = 100,
        t_run: float = 60.0,
        crossover_rate: float = 0.9,
        mutation_rate: float = 0.1,
        use_greedy_init: bool = True,
    ):
        self.inst = instance
        self.n_sol = n_sol
        self.t_run = t_run
        self.cx_rate = crossover_rate
        self.mut_rate = mutation_rate
        self.use_greedy_init = use_greedy_init
        self.evaluator = FitnessEvaluator(instance)
        self.parser = SolutionParser(instance)
        self.convergence: List[Tuple[float, float]] = []

    def _crossover(self, p1: Solution, p2: Solution) -> Solution:
        """SBX-like crossover on random keys."""
        nvar = p1.nvar
        mask = np.random.rand(nvar) < 0.5
        child_keys = np.where(mask, p1.keys, p2.keys)
        return Solution(keys=child_keys, n_customers=p1.n_customers,
                        n_vehicles=p1.n_vehicles)

    def _mutate(self, sol: Solution) -> Solution:
        """Polynomial-like mutation on random keys."""
        keys = sol.keys.copy()
        mask = np.random.rand(len(keys)) < self.mut_rate
        keys[mask] = np.random.rand(mask.sum())
        return Solution(keys=keys, n_customers=sol.n_customers,
                        n_vehicles=sol.n_vehicles)

    def _tournament(self, pop: List[Solution]) -> Solution:
        i, j = np.random.randint(0, len(pop), 2)
        if pop[i].rank < pop[j].rank:
            return pop[i]
        elif pop[i].rank > pop[j].rank:
            return pop[j]
        return pop[i] if pop[i].crowding_distance > pop[j].crowding_distance else pop[j]

    def run(self) -> Tuple[List[Solution], Dict]:
        logger.info("NSGA-II starting on %s", self.inst.name)

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
        start = time.time()
        gen = 0

        while time.time() - start < self.t_run:
            obj = np.array([s.objectives for s in pop])
            ranks, cds = assign_rank_and_crowding(obj)
            for i, s in enumerate(pop):
                s.rank = ranks[i]; s.crowding_distance = cds[i]

            elapsed = time.time() - start
            pf_idx = [i for i, r in enumerate(ranks) if r == 0]
            proxy = float(np.mean(obj[pf_idx, 0])) if pf_idx else float("inf")
            self.convergence.append((elapsed, proxy))

            offspring: List[Solution] = []
            for _ in range(self.n_sol):
                p1 = self._tournament(pop)
                p2 = self._tournament(pop)
                if np.random.random() < self.cx_rate:
                    child = self._crossover(p1, p2)
                else:
                    child = p1.clone()
                child = self._mutate(child)
                child.decode(); self.parser.parse(child)
                self.evaluator.evaluate(child)
                offspring.append(child)

            merged = pop + offspring
            merged_obj = np.array([s.objectives for s in merged])
            best = select_best(merged_obj, self.n_sol)
            pop = [merged[i] for i in best]
            gen += 1

        obj = np.array([s.objectives for s in pop])
        ranks, _ = assign_rank_and_crowding(obj)
        for i, s in enumerate(pop): s.rank = ranks[i]
        pareto = [s for s in pop if s.rank == 0]
        logger.info("NSGA-II done: %d gen, PF=%d", gen, len(pareto))
        return pareto, {"generations": gen, "runtime": time.time()-start,
                        "convergence": self.convergence}
