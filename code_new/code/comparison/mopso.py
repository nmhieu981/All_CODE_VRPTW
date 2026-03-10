"""
MOPSO — Multi-Objective Particle Swarm Optimization
====================================================
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
from algorithm.crowding import assign_rank_and_crowding, select_best, select_gbest
from algorithm.init_heuristics import greedy_nearest_neighbour

logger = logging.getLogger(__name__)


class MOPSO:
    """Multi-Objective PSO for MO-VRPTW."""

    def __init__(
        self,
        instance: VRPTWInstance,
        n_sol: int = 100,
        t_run: float = 60.0,
        w: float = 0.4,
        c1: float = 2.0,
        c2: float = 2.0,
        use_greedy_init: bool = True,
    ):
        self.inst = instance
        self.n_sol = n_sol
        self.t_run = t_run
        self.w = w
        self.c1 = c1
        self.c2 = c2
        self.use_greedy_init = use_greedy_init

        self.evaluator = FitnessEvaluator(instance)
        self.parser = SolutionParser(instance)
        self.convergence: List[Tuple[float, float]] = []

    def run(self) -> Tuple[List[Solution], Dict]:
        logger.info("MOPSO starting on %s", self.inst.name)

        # Init population
        pop: List[Solution] = []
        if self.use_greedy_init:
            nn_routes = greedy_nearest_neighbour(self.inst)
            x1 = Solution.from_routes(nn_routes, self.inst)
            x1.decode(); self.parser.parse(x1)
            pop.append(x1)
            start_idx = 1
        else:
            start_idx = 0

        for _ in range(start_idx, self.n_sol):
            s = Solution.random(self.inst)
            s.decode(); self.parser.parse(s)
            pop.append(s)

        self.evaluator.evaluate_batch(pop)

        # Velocities & personal bests
        nvar = pop[0].nvar
        velocities = [np.random.uniform(-0.1, 0.1, nvar) for _ in range(self.n_sol)]
        pbest = [s.clone() for s in pop]

        start = time.time()
        gen = 0

        while time.time() - start < self.t_run:
            obj = np.array([s.objectives for s in pop])
            ranks, cds = assign_rank_and_crowding(obj)
            pf_idx = [i for i, r in enumerate(ranks) if r == 0]
            pf_cds = cds[pf_idx]

            elapsed = time.time() - start
            pf_obj = obj[pf_idx]
            proxy = float(np.mean(pf_obj[:, 0])) if pf_idx else float("inf")
            self.convergence.append((elapsed, proxy))

            for i in range(self.n_sol):
                gb = pop[select_gbest(pf_idx, pf_cds)]
                r1, r2 = np.random.rand(nvar), np.random.rand(nvar)
                velocities[i] = (
                    self.w * velocities[i]
                    + self.c1 * r1 * (pbest[i].keys - pop[i].keys)
                    + self.c2 * r2 * (gb.keys - pop[i].keys)
                )
                new_keys = np.clip(pop[i].keys + velocities[i], 0, 1)
                yi = Solution(keys=new_keys, n_customers=pop[i].n_customers,
                              n_vehicles=pop[i].n_vehicles)
                yi.decode(); self.parser.parse(yi)
                self.evaluator.evaluate(yi)

                # Update personal best
                if yi.objectives < pbest[i].objectives:
                    pbest[i] = yi.clone()

                pop[i] = yi

            gen += 1

        obj = np.array([s.objectives for s in pop])
        ranks, _ = assign_rank_and_crowding(obj)
        for i, s in enumerate(pop): s.rank = ranks[i]
        pareto = [s for s in pop if s.rank == 0]
        logger.info("MOPSO done: %d gen, PF=%d", gen, len(pareto))
        return pareto, {"generations": gen, "runtime": time.time()-start,
                        "convergence": self.convergence}
