"""
A*-Based Search (ABS) — Preference-Aware Local Search
======================================================
Destroy-and-rebuild with regret-2 insertion, worst removal,
2-opt post-processing, and preference-guided scoring.
Based on Section 4.5, Tables 3–5 of Lai et al., Applied Soft Computing 2025.
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

import numpy as np

from core.problem import VRPTWInstance
from core.solution import Solution, SolutionParser


class ABSearch:
    """Destroy-and-rebuild local search with preference-aware heuristics."""

    def __init__(self, instance: VRPTWInstance, n_abs: float = 0.2,
                 preference=None):
        self.inst = instance
        self.n_abs = n_abs
        self.parser = SolutionParser(instance)
        self.pref = preference  # UserPreference or None

    # ----- trigger ----------------------------------------------------------
    def should_apply(self) -> bool:
        return np.random.random() < self.n_abs

    # ----- route selection (Eq 18) ------------------------------------------
    def select_routes_to_remove(self, routes: List[List[int]]) -> List[int]:
        """
        Select routes to destroy.
        Probability proportional to exp(-10 * nCus_k / max(nCus)).
        Chooses max(1, round(|τ|/3)) routes.
        """
        if not routes:
            return []

        n_cus = np.array([len(r) for r in routes], dtype=float)
        max_cus = n_cus.max()
        if max_cus == 0:
            return []

        probs = np.exp(-10.0 * n_cus / max_cus)
        probs /= probs.sum()

        n_remove = max(1, round(len(routes) / 3))
        n_remove = min(n_remove, len(routes))

        chosen = np.random.choice(
            len(routes), size=n_remove, replace=False, p=probs
        )
        return sorted(chosen.tolist(), reverse=True)

    # ----- worst removal — remove customers causing most distance -----------
    def worst_removal(self, routes: List[List[int]],
                      n_remove: int) -> Tuple[List[List[int]], List[int]]:
        """
        Remove the n_remove customers whose removal saves the most distance.
        """
        dm = self.inst.distance_matrix
        removal_savings: List[Tuple[float, int, int]] = []

        for ri, route in enumerate(routes):
            for ci, cid in enumerate(route):
                prev_id = 0 if ci == 0 else route[ci - 1]
                next_id = 0 if ci == len(route) - 1 else route[ci + 1]
                # Distance saved by removing cid
                saving = (dm[prev_id][cid] + dm[cid][next_id]
                          - dm[prev_id][next_id])
                removal_savings.append((saving, ri, cid))

        # Sort by saving descending — remove worst first
        removal_savings.sort(reverse=True)

        removed: List[int] = []
        removed_set = set()
        for saving, ri, cid in removal_savings:
            if len(removed) >= n_remove:
                break
            if cid not in removed_set:
                removed.append(cid)
                removed_set.add(cid)

        # Rebuild routes without removed customers
        new_routes = []
        for route in routes:
            new_r = [c for c in route if c not in removed_set]
            if new_r:
                new_routes.append(new_r)

        return new_routes, removed

    # ----- calVcost (Table 4) -----------------------------------------------
    def cal_vcost(
        self,
        customer_id: int,
        prev_id: int,
        current_time: float,
        current_load: float,
    ) -> float:
        """
        Feasibility check for inserting *customer_id* after *prev_id*.
        Returns 0 if feasible, inf otherwise.
        """
        cust = self.inst.customers[customer_id]
        depot = self.inst.depot

        # v1: capacity
        if current_load + cust.demand > self.inst.capacity:
            return float("inf")

        travel = self.inst.travel_time_matrix[prev_id][customer_id]
        arrival = current_time + travel
        start = max(arrival, cust.ready_time)

        # v2: customer time window
        if start > cust.due_date:
            return float("inf")

        # v3: can return to depot in time?
        return_time = start + cust.service_time + self.inst.travel_time_matrix[customer_id][0]
        if return_time > depot.due_date:
            return float("inf")

        return 0.0

    # ----- calHcost (Table 5) -----------------------------------------------
    def cal_hcost(
        self,
        candidate_id: int,
        open_customers: List[int],
        current_time_after: float,
        current_load_after: float,
    ) -> int:
        """
        Heuristic estimate: count how many remaining open customers
        could *still* be served after visiting candidate_id.
        """
        cust = self.inst.customers[candidate_id]
        start = max(current_time_after, cust.ready_time)
        time_after = start + cust.service_time
        load_after = current_load_after

        count = 0
        for cj in open_customers:
            if cj == candidate_id:
                continue
            c_next = self.inst.customers[cj]
            if load_after + c_next.demand > self.inst.capacity:
                continue
            travel_next = self.inst.travel_time_matrix[candidate_id][cj]
            arr_next = time_after + travel_next
            start_next = max(arr_next, c_next.ready_time)
            if start_next > c_next.due_date:
                continue
            ret = start_next + c_next.service_time + self.inst.travel_time_matrix[cj][0]
            if ret > self.inst.depot.due_date:
                continue
            count += 1

        return count

    # ----- build_route (Table 3) — enhanced with regret-2 -------------------
    def build_route(
        self,
        unassigned: List[int],
        avg_makespan: float,
    ) -> Tuple[List[int], List[int]]:
        """
        Build one route from *unassigned* customers using A*-style selection.
        Returns (route, remaining_unassigned).
        """
        route: List[int] = []
        current_time = 0.0
        current_load = 0.0
        prev_id = 0  # depot

        remaining = list(unassigned)

        while remaining:
            # Find feasible candidates (validcus)
            valid: List[int] = []
            for cid in remaining:
                vc = self.cal_vcost(cid, prev_id, current_time, current_load)
                if vc < float("inf"):
                    valid.append(cid)

            if not valid:
                break

            # Stopping criteria 3: makespan balance
            if route and current_time >= avg_makespan:
                break

            # Compute g-costs, h-costs, and preference-aware scores
            g_costs = []
            h_costs = []
            tw_urgency = []   # time window tightness (for w2)
            for cid in valid:
                g_c = self.inst.distance_matrix[prev_id][cid]
                g_costs.append(g_c)

                cust = self.inst.customers[cid]
                travel = self.inst.travel_time_matrix[prev_id][cid]
                arrival = current_time + travel
                start = max(arrival, cust.ready_time)
                time_after = start + cust.service_time
                load_after = current_load + cust.demand

                h_c = self.cal_hcost(cid, remaining, time_after, load_after)
                h_costs.append(h_c)

                # TW tightness: narrower window → more urgent
                tw_width = max(1.0, cust.due_date - cust.ready_time)
                tw_urgency.append(1.0 / tw_width)

            g_arr = np.array(g_costs)
            h_arr = np.array(h_costs, dtype=float)
            tw_arr = np.array(tw_urgency)

            # Normalise g (distance component)
            g_max = g_arr.max()
            g_sc = g_arr / g_max if g_max > 0 else np.zeros_like(g_arr)

            # Invert & normalise h (reachability component)
            h_max = h_arr.max()
            h_sc = (h_max - h_arr) / h_max if h_max > 0 else np.zeros_like(h_arr)

            # Normalise tw urgency
            tw_max = tw_arr.max()
            tw_sc = tw_arr / tw_max if tw_max > 0 else np.zeros_like(tw_arr)

            # Preference-weighted composite score
            if self.pref is not None:
                w = self.pref.w
                # w[0]=distance weight, w[1]=waiting/TW weight, w[2]=balance weight
                f = w[0] * g_sc + w[1] * tw_sc + (1.0 - w[0] - w[1]) * h_sc
            else:
                f = g_sc + h_sc

            f_max = f.max()
            if f_max > 0:
                f = f_max - f  # invert so lower f → higher probability
            f += 1e-10  # avoid zero probabilities

            # Roulette-wheel selection
            probs = f / f.sum()
            chosen_local = np.random.choice(len(valid), p=probs)
            chosen_cid = valid[chosen_local]

            # Update route state
            cust = self.inst.customers[chosen_cid]
            travel = self.inst.travel_time_matrix[prev_id][chosen_cid]
            arrival = current_time + travel
            start = max(arrival, cust.ready_time)
            current_time = start + cust.service_time
            current_load += cust.demand
            prev_id = chosen_cid

            route.append(chosen_cid)
            remaining.remove(chosen_cid)

        return route, remaining

    # ----- regret-2 insertion -----------------------------------------------
    def regret_insertion(self, routes: List[List[int]],
                         unassigned: List[int]) -> List[List[int]]:
        """
        Insert unassigned customers using regret-2 heuristic.
        Prioritises customers that have the largest difference between
        their best and second-best insertion cost.
        """
        from algorithm.init_heuristics import evaluate_route

        remaining = list(unassigned)
        routes = [list(r) for r in routes]

        while remaining:
            regrets: List[Tuple[float, int, int, int]] = []  # (regret, cid, best_ri, best_pos)

            for cid in remaining:
                costs: List[Tuple[float, int, int]] = []  # (cost, ri, pos)

                for ri, route in enumerate(routes):
                    _, old_d, _ = evaluate_route(route, self.inst)
                    for pos in range(len(route) + 1):
                        cand = route[:pos] + [cid] + route[pos:]
                        ok, d, _ = evaluate_route(cand, self.inst)
                        if ok:
                            costs.append((d - old_d, ri, pos))

                if not costs:
                    # No feasible insertion → new route
                    regrets.append((float("inf"), cid, -1, -1))
                    continue

                costs.sort(key=lambda x: x[0])
                best_cost, best_ri, best_pos = costs[0]

                if len(costs) >= 2:
                    regret = costs[1][0] - best_cost
                else:
                    regret = 1e6  # high regret → insert urgently

                regrets.append((regret, cid, best_ri, best_pos))

            if not regrets:
                break

            # Sort by regret descending — most urgent first
            regrets.sort(reverse=True)
            _, chosen_cid, best_ri, best_pos = regrets[0]

            if best_ri >= 0:
                routes[best_ri].insert(best_pos, chosen_cid)
            else:
                routes.append([chosen_cid])

            remaining.remove(chosen_cid)

        return routes

    # ----- quick 2-opt on a single route ------------------------------------
    def _quick_two_opt(self, route: List[int]) -> List[int]:
        """Fast 2-opt without repeated passes (single pass)."""
        from algorithm.init_heuristics import evaluate_route

        best = list(route)
        _, best_d, _ = evaluate_route(best, self.inst)

        for i in range(len(best) - 1):
            for j in range(i + 1, len(best)):
                cand = best[:i] + best[i:j+1][::-1] + best[j+1:]
                ok, d, _ = evaluate_route(cand, self.inst)
                if ok and d < best_d - 1e-10:
                    best = cand
                    best_d = d
        return best

    # ----- main ABS application — enhanced ----------------------------------
    def apply(self, solution: Solution) -> Solution:
        """
        Destroy selected routes, then rebuild using build_route()
        with regret-2 insertion and 2-opt post-processing.
        """
        new_sol = solution.clone()
        if new_sol.routes is None:
            new_sol.decode()
        self.parser.parse(new_sol)

        routes = new_sol.routes if new_sol.routes else []
        if not routes:
            return new_sol

        # Choose destruction method
        use_worst = np.random.random() < 0.4  # 40% worst removal

        if use_worst:
            # Worst removal: remove customers causing most distance
            all_cus = sum(len(r) for r in routes)
            n_remove = max(1, int(all_cus * np.random.uniform(0.15, 0.35)))
            kept_routes, unassigned_list = self.worst_removal(routes, n_remove)
            unassigned: List[int] = list(new_sol.unassigned) + unassigned_list
        else:
            # Original: remove routes
            remove_indices = self.select_routes_to_remove(routes)
            unassigned = list(new_sol.unassigned)
            kept_routes: List[List[int]] = []
            for i, route in enumerate(routes):
                if i in remove_indices:
                    unassigned.extend(route)
                else:
                    kept_routes.append(route)

        # Compute average makespan of kept routes for stopping criterion
        avg_msp = 0.0
        if kept_routes:
            completion_times = []
            for r in kept_routes:
                _, _, ct = self.parser.route_details(r)
                completion_times.append(ct)
            avg_msp = np.mean(completion_times)

        # Rebuild routes
        new_routes = list(kept_routes)
        max_new = self.inst.n_vehicles - len(new_routes)
        attempts = 0

        while unassigned and attempts < max_new:
            built, unassigned = self.build_route(unassigned, avg_msp)
            if built:
                new_routes.append(built)
            else:
                break
            attempts += 1

        # If still unassigned, try regret insertion
        if unassigned:
            new_routes = self.regret_insertion(new_routes, unassigned)
            # Recheck unassigned
            served = set()
            for r in new_routes:
                served.update(r)
            unassigned = [c for c in unassigned if c not in served]

        # Post-processing: quick 2-opt on rebuilt routes
        new_routes = [self._quick_two_opt(r) for r in new_routes if r]

        # Re-encode as random keys
        result = Solution.from_routes(new_routes, self.inst)
        result.unassigned = unassigned
        result.restcus = len(unassigned)
        return result
