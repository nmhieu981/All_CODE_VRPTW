"""
iNSSSO — Preference-Based improved NSSSO
==========================================
Enhanced with:
  - R-Dominance ranking (preference-guided non-dominated sorting)
  - ASF-based gBest selection (Achievement Scalarizing Function)
  - External ε-dominance archive with preference tie-breaking
  - Adaptive operator rates (ABS/LS probabilities adjust dynamically)
  - Polynomial mutation for diversity
  - Preference-aware convergence tracking
Optimised for near-optimal solutions on Solomon VRPTW benchmarks.
"""

from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional, Tuple

import numpy as np

from core.problem import VRPTWInstance
from core.solution import Solution, SolutionParser
from core.objectives import FitnessEvaluator
from core.preference import UserPreference
from algorithm.nondominated import fast_nondominated_sort, is_dominated_by_set
from algorithm.crowding import (
    assign_rank_and_crowding,
    crowding_distance,
    select_best,
    select_gbest,
)
from algorithm.r_dominance import (
    r_assign_rank_and_crowding,
    select_best_r,
    select_gbest_asf,
)
from algorithm.abs_search import ABSearch
from algorithm.init_heuristics import (
    best_initialization,
    greedy_nearest_neighbour,
    insertion_heuristic,
    clarke_wright_savings,
    full_local_search,
    two_opt_route,
    or_opt_route,
    evaluate_route,
    total_distance,
    merge_routes,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
#  External Archive with ε-dominance + Preference
# ═══════════════════════════════════════════════════════════════════
class ParetoArchive:
    """
    Bounded external archive using ε-dominance.
    When preference is set, uses ASF for tie-breaking within ε-boxes.
    """

    def __init__(self, max_size: int = 200, epsilon: float = 0.001,
                 pref: Optional[UserPreference] = None):
        self.max_size = max_size
        self.epsilon = epsilon
        self.solutions: List[Solution] = []
        self.pref = pref

    def _eps_box(self, obj: np.ndarray) -> np.ndarray:
        """Map objectives to ε-box indices."""
        return np.floor(obj / (self.epsilon + 1e-15))

    def update(self, candidates: List[Solution]) -> None:
        """Add candidates to archive, removing dominated members."""
        for sol in candidates:
            if sol.objectives is None:
                continue
            self._try_add(sol)

        if len(self.solutions) > self.max_size:
            self._prune()

    def _try_add(self, sol: Solution) -> None:
        """Try to add a solution to the archive."""
        obj = np.array(sol.objectives)
        eps_box = self._eps_box(obj)

        to_remove = []
        for i, member in enumerate(self.solutions):
            m_obj = np.array(member.objectives)
            m_box = self._eps_box(m_obj)

            # Same ε-box → keep the one with better ASF (or smaller sum)
            if np.array_equal(eps_box, m_box):
                if self.pref is not None:
                    if self.pref.asf(obj) < self.pref.asf(m_obj):
                        to_remove.append(i)
                    else:
                        return
                else:
                    if sum(sol.objectives) < sum(member.objectives):
                        to_remove.append(i)
                    else:
                        return
            # New solution is dominated
            elif np.all(m_obj <= obj) and np.any(m_obj < obj):
                return
            # New solution dominates existing
            elif np.all(obj <= m_obj) and np.any(obj < m_obj):
                to_remove.append(i)

        for i in sorted(to_remove, reverse=True):
            self.solutions.pop(i)

        self.solutions.append(sol.clone())

    def _prune(self) -> None:
        """Prune archive: prefer solutions with lower ASF, then crowding."""
        if len(self.solutions) <= self.max_size:
            return

        objs = np.array([s.objectives for s in self.solutions])

        if self.pref is not None:
            # Sort by ASF score, keep top max_size
            asf_vals = self.pref.asf_augmented_batch(objs)
            sorted_idx = np.argsort(asf_vals)[:self.max_size]
        else:
            indices = list(range(len(self.solutions)))
            cds = crowding_distance(objs, indices, normalize=True)
            sorted_idx = np.argsort(-cds)[:self.max_size]

        self.solutions = [self.solutions[i] for i in sorted_idx]

    def get_solutions(self) -> List[Solution]:
        return list(self.solutions)

    def size(self) -> int:
        return len(self.solutions)


class iNSSSO:
    """
    Preference-based improved NSSSO with R-Dominance ranking,
    ASF-based gBest selection, and preference-aware ABS.
    """

    def __init__(
        self,
        instance: VRPTWInstance,
        n_sol: int = 100,
        cw: float = 0.99,
        cg: float = 0.95,
        n_abs: float = 0.2,
        t_run: float = 60.0,
        archive_size: int = 200,
        epsilon: float = 0.001,
        ls_rate_rank0: float = 0.10,
        mutation_rate: float = 0.05,
        preference: Optional[UserPreference] = None,
    ):
        self.inst = instance
        self.n_sol = n_sol
        self.cw = cw
        self.cg = cg
        self.n_abs_base = n_abs
        self.n_abs = n_abs
        self.t_run = t_run
        self.ls_rate_rank0 = ls_rate_rank0
        self.mutation_rate = mutation_rate
        self.pref = preference

        self.evaluator = FitnessEvaluator(instance)
        self.parser = SolutionParser(instance)
        self.abs_search = ABSearch(instance, n_abs, preference=preference)

        self.archive = ParetoArchive(
            max_size=archive_size, epsilon=epsilon, pref=preference
        )
        self.population: List[Solution] = []
        self.convergence: List[Tuple[float, float]] = []

        # Adaptive tracking
        self._stagnation_count = 0
        self._last_best_asf = float("inf")

    def _auto_calibrate_preference(self) -> None:
        """
        Auto-calibrate reference point g from initial population.

        Strategy: g = ideal + margin * (p10 - ideal)
        - ideal = best value per objective among feasible solutions
        - p10 = 10th percentile (near-best, not outlier)
        - margin = 0.1 (slightly relaxed aspiration)
        This makes g instance-adaptive — works for C101, R101, etc.
        """
        if self.pref is None:
            return

        # Only use feasible solutions (no unserved customers)
        feasible = [s for s in self.population
                    if s.objectives is not None and s.restcus == 0]

        if len(feasible) < 3:
            # Fallback: use all solutions but cap at reasonable values
            feasible = [s for s in self.population
                        if s.objectives is not None]

        if len(feasible) == 0:
            return

        objs = np.array([s.objectives for s in feasible])

        ideal = objs.min(axis=0)
        p10 = np.percentile(objs, 10, axis=0)

        # g = ideal + small margin towards p10
        margin = 0.1
        new_g = ideal + margin * np.maximum(p10 - ideal, 0.0)

        # Ensure g is slightly above ideal (at least 1% of range)
        obj_range = objs.max(axis=0) - ideal
        min_shift = 0.01 * obj_range
        new_g = np.maximum(new_g, ideal + min_shift)

        self.pref.g = new_g

        # Update ABS search preference too
        self.abs_search.pref = self.pref
        self.archive.pref = self.pref

        logger.info("Auto-calibrated g = [%.2f, %.4f, %.6f] (from %d feasible)",
                    new_g[0], new_g[1], new_g[2], len(feasible))

    # ----- initialisation ---------------------------------------------------
    def initialize_population(self) -> List[Solution]:
        """Multi-start initialisation with heavy local search."""
        pop: List[Solution] = []

        # Best init with local search
        init_time = min(self.t_run * 0.4, 15.0)
        best_routes = best_initialization(self.inst, time_limit=init_time)

        # Smart merge: only when capacity utilization is low (RC-type)
        total_demand = sum(self.inst.customers[c].demand
                          for r in best_routes for c in r)
        avg_util = total_demand / (len(best_routes) * self.inst.capacity)
        if avg_util < 0.6:  # spare capacity → try merging
            best_routes = merge_routes(best_routes, self.inst)
            logger.info("Route merge: %d routes (util=%.0f%%)",
                        len(best_routes), avg_util * 100)

        best_dist = total_distance(best_routes, self.inst)

        x1 = Solution.from_routes(best_routes, self.inst)
        x1.decode()
        self.parser.parse(x1)
        self.evaluator.evaluate(x1)
        pop.append(x1)
        logger.info("Best init: %d routes, dist=%.1f",
                    len(best_routes), best_dist)

        # Generate diverse seeds from different strategies
        seed_routes_list: List[List[List[int]]] = [best_routes]

        for sort_key in ["ready_time", "distance", "angle", "demand",
                         "due_date", "tw_center"]:
            try:
                r = insertion_heuristic(self.inst, sort_key=sort_key)
                r = [two_opt_route(rt, self.inst) for rt in r]
                seed_routes_list.append(r)
            except Exception:
                pass

        try:
            cw_routes = clarke_wright_savings(self.inst)
            cw_routes = [two_opt_route(r, self.inst) for r in cw_routes]
            seed_routes_list.append(cw_routes)
        except Exception:
            pass

        try:
            nn_routes = greedy_nearest_neighbour(self.inst)
            nn_routes = [two_opt_route(r, self.inst) for r in nn_routes]
            seed_routes_list.append(nn_routes)
        except Exception:
            pass

        # Create solutions from seeds + perturbations
        for seed in seed_routes_list:
            if len(pop) >= self.n_sol:
                break
            sol = Solution.from_routes(seed, self.inst)
            sol.decode()
            self.parser.parse(sol)
            self.evaluator.evaluate(sol)
            pop.append(sol)

            for noise_scale in [0.05, 0.10, 0.15]:
                if len(pop) >= self.n_sol:
                    break
                ps = self._perturb_solution(sol, noise_scale)
                ps.decode()
                self.parser.parse(ps)
                self.evaluator.evaluate(ps)
                pop.append(ps)

        # Fill remaining with random
        while len(pop) < self.n_sol:
            sol = Solution.random(self.inst)
            sol.decode()
            self.parser.parse(sol)
            self.evaluator.evaluate(sol)
            pop.append(sol)

        return pop

    def _perturb_solution(self, sol: Solution,
                          noise_scale: float = 0.08) -> Solution:
        """Create a perturbed copy of a solution's keys."""
        noise = np.random.uniform(-noise_scale, noise_scale, len(sol.keys))
        new_keys = np.clip(sol.keys + noise, 0.0, 0.999)
        return Solution(
            keys=new_keys,
            n_customers=sol.n_customers,
            n_vehicles=sol.n_vehicles,
        )

    # ----- SSO update (Eq 2) — vectorised -----------------------------------
    def update_solution(self, xi: Solution, gbest: Solution) -> Solution:
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

    # ----- polynomial mutation (from NSGA-II) --------------------------------
    def _polynomial_mutation(self, sol: Solution, eta_m: float = 20.0) -> Solution:
        """Apply polynomial mutation to random keys for diversity."""
        keys = sol.keys.copy()
        for j in range(len(keys)):
            if np.random.random() < self.mutation_rate:
                y = keys[j]
                delta1 = y - 0.0
                delta2 = 1.0 - y
                rnd = np.random.random()
                if rnd < 0.5:
                    xy = 1.0 - delta1
                    val = 2.0 * rnd + (1.0 - 2.0 * rnd) * (xy ** (eta_m + 1.0))
                    deltaq = val ** (1.0 / (eta_m + 1.0)) - 1.0
                else:
                    xy = 1.0 - delta2
                    val = 2.0 * (1.0 - rnd) + 2.0 * (rnd - 0.5) * (xy ** (eta_m + 1.0))
                    deltaq = 1.0 - val ** (1.0 / (eta_m + 1.0))
                keys[j] = np.clip(y + deltaq, 0.0, 0.999)

        return Solution(
            keys=keys,
            n_customers=sol.n_customers,
            n_vehicles=sol.n_vehicles,
        )

    # ----- local search on decoded solution ---------------------------------
    def apply_local_search(self, solution: Solution) -> Solution:
        """Apply 2-opt + smart route merge to decoded routes."""
        if solution.routes is None or solution.restcus > 0:
            return solution
        routes = [two_opt_route(r, self.inst) for r in solution.routes]

        # Smart merge: only when spare capacity exists
        total_demand = sum(self.inst.customers[c].demand
                          for r in routes for c in r)
        if routes:
            avg_util = total_demand / (len(routes) * self.inst.capacity)
            if avg_util < 0.6:
                routes = merge_routes(routes, self.inst, max_attempts=2)

        result = Solution.from_routes(routes, self.inst)
        result.decode()
        self.parser.parse(result)
        return result

    # ----- adaptive parameter control ----------------------------------------
    def _adapt_parameters(self, gen: int, progress: float) -> None:
        """Adapt ABS probability based on search progress and stagnation."""
        # Check stagnation using ASF (preference-aware)
        current_pf = [s for s in self.population if s.rank == 0]
        if current_pf:
            if self.pref is not None:
                best_asf = min(self.pref.asf(s.objectives) for s in current_pf)
            else:
                best_asf = min(s.objectives[0] for s in current_pf)

            if abs(best_asf - self._last_best_asf) < 1e-6:
                self._stagnation_count += 1
            else:
                self._stagnation_count = 0
                self._last_best_asf = best_asf

        # Increase ABS probability when stagnating
        if self._stagnation_count > 5:
            self.n_abs = min(0.5, self.n_abs_base + 0.05 * self._stagnation_count)
        else:
            self.n_abs = self.n_abs_base

        # Increase mutation rate in later stages
        self.mutation_rate = 0.05 + 0.10 * progress

    # ----- main loop --------------------------------------------------------
    def run(self) -> Tuple[List[Solution], Dict]:
        """Main loop: fast Pareto sort + ASF-based gBest (hybrid)."""
        pref_str = ""
        if self.pref is not None:
            pref_str = f", g={self.pref.g.tolist()}, w={self.pref.w.tolist()}"
        logger.info("iNSSSO starting on %s  (nSol=%d, tRun=%.0fs, nABS=%.2f%s)",
                     self.inst.name, self.n_sol, self.t_run, self.n_abs, pref_str)

        # 1. Initialise
        self.population = self.initialize_population()

        # Auto-calibrate reference point from initial population
        self._auto_calibrate_preference()

        self.archive.update(self.population)

        start = time.time()
        generation = 0

        while True:
            elapsed = time.time() - start
            if elapsed >= self.t_run:
                break
            progress = elapsed / self.t_run

            # ── Ranking: always use fast standard Pareto sort ──
            obj_matrix = np.array([s.objectives for s in self.population])
            ranks, cds = assign_rank_and_crowding(obj_matrix)

            for i, sol in enumerate(self.population):
                sol.rank = ranks[i]
                sol.crowding_distance = cds[i]

            pf_indices = [i for i, r in enumerate(ranks) if r == 0]
            pf_cds = cds[pf_indices]

            # Convergence tracking (ASF-based when preference set)
            if pf_indices:
                pf_obj = obj_matrix[pf_indices]
                if self.pref is not None:
                    asf_vals = self.pref.asf_batch(pf_obj)
                    conv_metric = float(np.min(asf_vals))
                else:
                    conv_metric = float(np.mean(pf_obj[:, 0]))
            else:
                conv_metric = float("inf")
            self.convergence.append((elapsed, conv_metric))

            # Adapt parameters
            self._adapt_parameters(generation, progress)
            self.abs_search.n_abs = self.n_abs

            # ── Generate offspring ──
            route_counts = np.array([len(s.routes) if s.routes else float('inf') for s in self.population])
            offspring: List[Solution] = []
            for i in range(self.n_sol):
                if np.random.random() < self.n_abs:
                    # ABS local search (preference-aware)
                    yi = self.abs_search.apply(self.population[i])
                else:
                    # gBest selection: ASF-based or crowding-based
                    if self.pref is not None:
                        gb_idx = select_gbest_asf(
                            obj_matrix, self.pref, pf_indices, route_counts
                        )
                    else:
                        gb_idx = select_gbest(pf_indices, pf_cds, route_counts)

                    gbest = self.population[gb_idx]
                    yi = self.update_solution(self.population[i], gbest)

                    # Polynomial mutation — mainly when stagnating
                    if self._stagnation_count > 3 and np.random.random() < self.mutation_rate:
                        yi = self._polynomial_mutation(yi)

                yi.decode()
                self.parser.parse(yi)
                self.evaluator.evaluate(yi)

                # Adaptive local search on good offspring
                rank_i = ranks[i] if i < len(ranks) else 1
                ls_prob = self.ls_rate_rank0 if rank_i == 0 else 0.03
                if yi.restcus == 0 and np.random.random() < ls_prob:
                    yi = self.apply_local_search(yi)
                    self.evaluator.evaluate(yi)

                offspring.append(yi)

            # Update archive
            self.archive.update(offspring)

            # Inject archive solution for diversity
            archive_sols = self.archive.get_solutions()
            if archive_sols:
                inject_idx = np.random.randint(len(archive_sols))
                injected = archive_sols[inject_idx].clone()
                if injected.objectives is None:
                    injected.decode()
                    self.parser.parse(injected)
                    self.evaluator.evaluate(injected)
                offspring.append(injected)

            # ── Selection: fast Pareto sort (preference via gBest/archive) ──
            merged = self.population + offspring
            merged_obj = np.array([s.objectives for s in merged])
            merged_routes = np.array([len(s.routes) if s.routes else float('inf') for s in merged])
            best_indices = select_best(merged_obj, self.n_sol, merged_routes)

            self.population = [merged[i] for i in best_indices]
            generation += 1

        # ── Final ranking ──
        obj_matrix = np.array([s.objectives for s in self.population])
        ranks, cds = assign_rank_and_crowding(obj_matrix)

        for i, sol in enumerate(self.population):
            sol.rank = ranks[i]
            sol.crowding_distance = cds[i]

        self.archive.update(self.population)

        # Return archive as the Pareto front
        pareto = self.archive.get_solutions()
        if not pareto:
            pareto = [s for s in self.population if s.rank == 0]

        elapsed = time.time() - start
        logger.info("iNSSSO finished: %d gen, %.1fs, PF=%d (archive=%d)",
                     generation, elapsed, len(pareto), self.archive.size())

        return pareto, {
            "generations": generation,
            "runtime": elapsed,
            "convergence": self.convergence,
        }
