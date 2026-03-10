"""
SPEA2 — Strength Pareto Evolutionary Algorithm 2
=================================================
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
from algorithm.crowding import assign_rank_and_crowding
from algorithm.nondominated import dominates
from algorithm.init_heuristics import greedy_nearest_neighbour

logger = logging.getLogger(__name__)


class SPEA2:
    """SPEA2 for MO-VRPTW."""

    def __init__(
        self,
        instance: VRPTWInstance,
        n_sol: int = 100,
        archive_size: int = 100,
        t_run: float = 60.0,
        crossover_rate: float = 0.9,
        mutation_rate: float = 0.1,
        use_greedy_init: bool = True,
    ):
        self.inst = instance
        self.n_sol = n_sol
        self.archive_size = archive_size
        self.t_run = t_run
        self.cx_rate = crossover_rate
        self.mut_rate = mutation_rate
        self.use_greedy_init = use_greedy_init
        self.evaluator = FitnessEvaluator(instance)
        self.parser = SolutionParser(instance)
        self.convergence: List[Tuple[float, float]] = []

    def _fitness_assignment(self, objectives: np.ndarray) -> np.ndarray:
        """SPEA2 fitness: strength + density."""
        n = len(objectives)
        strength = np.zeros(n)
        for i in range(n):
            for j in range(n):
                if i != j and dominates(tuple(objectives[i]), tuple(objectives[j])):
                    strength[i] += 1

        raw = np.zeros(n)
        for i in range(n):
            for j in range(n):
                if i != j and dominates(tuple(objectives[j]), tuple(objectives[i])):
                    raw[i] += strength[j]

        # Density (k-th nearest neighbour, k = sqrt(n))
        k = max(1, int(np.sqrt(n)))
        dists = np.zeros((n, n))
        for i in range(n):
            for j in range(n):
                dists[i, j] = np.linalg.norm(objectives[i] - objectives[j])

        density = np.zeros(n)
        for i in range(n):
            sorted_d = np.sort(dists[i])
            sigma_k = sorted_d[min(k, n - 1)]
            density[i] = 1.0 / (sigma_k + 2.0)

        return raw + density

    def _tournament(self, pop: List[Solution], fitness: np.ndarray) -> Solution:
        i, j = np.random.randint(0, len(pop), 2)
        return pop[i] if fitness[i] < fitness[j] else pop[j]

    def run(self) -> Tuple[List[Solution], Dict]:
        logger.info("SPEA2 starting on %s", self.inst.name)

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
        archive: List[Solution] = []

        start = time.time()
        gen = 0

        while time.time() - start < self.t_run:
            # Combine population and archive
            combined = pop + archive
            obj = np.array([s.objectives for s in combined])
            fitness = self._fitness_assignment(obj)

            elapsed = time.time() - start
            ranks, _ = assign_rank_and_crowding(obj)
            pf_idx = [i for i, r in enumerate(ranks) if r == 0]
            proxy = float(np.mean(obj[pf_idx, 0])) if pf_idx else float("inf")
            self.convergence.append((elapsed, proxy))

            # Update archive: select non-dominated + best
            nd_idx = [i for i in range(len(combined)) if fitness[i] < 1.0]
            if len(nd_idx) > self.archive_size:
                # Truncate by k-th nearest
                nd_fit = fitness[nd_idx]
                order = np.argsort(nd_fit)
                nd_idx = [nd_idx[order[i]] for i in range(self.archive_size)]
            elif len(nd_idx) < self.archive_size:
                dominated = [i for i in range(len(combined)) if i not in nd_idx]
                dominated.sort(key=lambda x: fitness[x])
                need = self.archive_size - len(nd_idx)
                nd_idx.extend(dominated[:need])

            archive = [combined[i].clone() for i in nd_idx]

            # Generate offspring via tournament on archive
            arch_obj = np.array([s.objectives for s in archive])
            arch_fit = self._fitness_assignment(arch_obj)

            offspring: List[Solution] = []
            for _ in range(self.n_sol):
                p1 = self._tournament(archive, arch_fit)
                p2 = self._tournament(archive, arch_fit)
                nvar = p1.nvar
                if np.random.random() < self.cx_rate:
                    mask = np.random.rand(nvar) < 0.5
                    child_keys = np.where(mask, p1.keys, p2.keys)
                else:
                    child_keys = p1.keys.copy()
                m_mask = np.random.rand(nvar) < self.mut_rate
                child_keys[m_mask] = np.random.rand(m_mask.sum())
                child = Solution(keys=child_keys, n_customers=p1.n_customers,
                                 n_vehicles=p1.n_vehicles)
                child.decode(); self.parser.parse(child)
                self.evaluator.evaluate(child)
                offspring.append(child)

            pop = offspring
            gen += 1

        # Final archive
        obj = np.array([s.objectives for s in archive])
        ranks, _ = assign_rank_and_crowding(obj)
        for i, s in enumerate(archive): s.rank = ranks[i]
        pareto = [s for s in archive if s.rank == 0]
        logger.info("SPEA2 done: %d gen, PF=%d", gen, len(pareto))
        return pareto, {"generations": gen, "runtime": time.time()-start,
                        "convergence": self.convergence}
