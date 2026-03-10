"""
Solution Representation  (Random-Key Encoding)
===============================================
Section 4.1 – 4.3 of Lai et al., Applied Soft Computing 2025.

Encoding
--------
A solution is a real vector  X = (x_1 … x_nVar)  where
    nVar = |V| + |C| − 1     (vehicles + customers − 1).

Decoding
--------
1. Argsort X  →  Z  (1-indexed integer sequence).
2. Values in Z greater than |C| are route separators.
3. The remaining values form customer-visit sequences per route.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np

from core.problem import VRPTWInstance, Customer


# ---------------------------------------------------------------------------
# Solution
# ---------------------------------------------------------------------------
@dataclass
class Solution:
    """Random-key encoded solution for MO-VRPTW."""

    keys: np.ndarray                        # real-valued vector [0, 1)
    n_customers: int
    n_vehicles: int

    # Cached decoded information (filled after decode / parse)
    routes: Optional[List[List[int]]] = field(default=None, repr=False)
    objectives: Optional[Tuple[float, float, float]] = field(default=None)
    rank: int = 0
    crowding_distance: float = 0.0

    # Infeasibility bookkeeping
    restcus: int = 0                        # # unserved customers
    unassigned: List[int] = field(default_factory=list)

    # ----- properties -------------------------------------------------------
    @property
    def nvar(self) -> int:
        return self.n_customers + self.n_vehicles - 1

    # ----- factory methods --------------------------------------------------
    @classmethod
    def random(cls, instance: VRPTWInstance) -> "Solution":
        """Create a random-key solution."""
        n_c = instance.n_customers
        n_v = instance.n_vehicles
        nvar = n_c + n_v - 1
        keys = np.random.rand(nvar)
        return cls(keys=keys, n_customers=n_c, n_vehicles=n_v)

    @classmethod
    def from_routes(cls, routes: List[List[int]], instance: VRPTWInstance) -> "Solution":
        """
        Convert a route-set into a random-key solution (reverse encoding).

        We need:  argsort(keys) + 1 == z_seq
        i.e., position z_seq[i]-1 must have the i-th smallest key.
        """
        n_c = instance.n_customers
        n_v = instance.n_vehicles
        nvar = n_c + n_v - 1

        # Collect all customers from routes
        all_customers: List[int] = []
        for route in routes:
            all_customers.extend(route)

        # Available separator values: n_c+1 .. nvar (= n_c + n_v - 1)
        all_separators = list(range(n_c + 1, nvar + 1))
        sep_idx = 0

        # Build integer sequence Z: customers interleaved with separators
        z_seq: List[int] = []
        for idx, route in enumerate(routes):
            z_seq.extend(route)
            if idx < len(routes) - 1 and sep_idx < len(all_separators):
                z_seq.append(all_separators[sep_idx])
                sep_idx += 1

        # Pad remaining separators at end
        while len(z_seq) < nvar and sep_idx < len(all_separators):
            z_seq.append(all_separators[sep_idx])
            sep_idx += 1

        # Truncate if somehow over nvar (shouldn't happen but safety)
        z_seq = z_seq[:nvar]

        # Assign keys so that argsort(keys)+1 == z_seq
        keys = np.zeros(nvar)
        for rank, z_val in enumerate(z_seq):
            pos = z_val - 1  # convert to 0-indexed position
            if 0 <= pos < nvar:
                lo = rank / nvar
                hi = (rank + 1) / nvar
                keys[pos] = np.random.uniform(lo, hi)

        sol = cls(keys=keys, n_customers=n_c, n_vehicles=n_v)
        sol.routes = [list(r) for r in routes]
        return sol

    # ----- encode / decode --------------------------------------------------
    def decode(self) -> List[List[int]]:
        """
        Decode random keys → route list.

        Returns a list of routes; each route is a list of customer ids
        (1-indexed, depot = 0 excluded).
        """
        z = np.argsort(self.keys) + 1       # 1-indexed

        routes: List[List[int]] = []
        current_route: List[int] = []
        for val in z:
            if val > self.n_customers:       # separator
                if current_route:
                    routes.append(current_route)
                    current_route = []
            else:
                current_route.append(int(val))
        if current_route:
            routes.append(current_route)

        self.routes = routes
        return routes

    # ----- clone ------------------------------------------------------------
    def clone(self) -> "Solution":
        new = Solution(
            keys=self.keys.copy(),
            n_customers=self.n_customers,
            n_vehicles=self.n_vehicles,
        )
        if self.routes is not None:
            new.routes = [list(r) for r in self.routes]
        if self.objectives is not None:
            new.objectives = self.objectives
        new.rank = self.rank
        new.crowding_distance = self.crowding_distance
        new.restcus = self.restcus
        new.unassigned = list(self.unassigned)
        return new


# ---------------------------------------------------------------------------
# Solution Parser — validates feasibility and computes route details
# ---------------------------------------------------------------------------
class SolutionParser:
    """
    Parse decoded routes: validate time-windows & capacity,
    compute waiting times and completion times (Section 4.3).
    """

    def __init__(self, instance: VRPTWInstance):
        self.inst = instance

    def parse(self, solution: Solution) -> Solution:
        """
        Validate and repair solution in-place.
        Infeasible customers AND customers missing from decoded routes
        are moved to ``solution.unassigned``.
        """
        if solution.routes is None:
            solution.decode()

        feasible_routes: List[List[int]] = []
        unassigned: List[int] = []

        for route in solution.routes:
            feasible, infeasible = self._validate_route(route)
            if feasible:
                feasible_routes.append(feasible)
            unassigned.extend(infeasible)

        # Detect customers not present in ANY feasible route
        served = set()
        for route in feasible_routes:
            served.update(route)
        all_customers = set(range(1, solution.n_customers + 1))
        missing = all_customers - served - set(unassigned)
        unassigned.extend(missing)

        solution.routes = feasible_routes
        solution.unassigned = unassigned
        solution.restcus = len(unassigned)
        return solution

    # ----- internal ----------------------------------------------------------
    def _validate_route(self, route: List[int]):
        """
        Walk along a route checking capacity and time-window constraints.

        Returns (feasible_customers, infeasible_customers).
        """
        inst = self.inst
        depot = inst.depot
        feasible: List[int] = []
        infeasible: List[int] = []

        load = 0.0
        current_time = 0.0
        prev_id = 0  # depot

        for cid in route:
            cust = inst.customers[cid]
            travel = inst.travel_time_matrix[prev_id][cid]
            arrival = current_time + travel

            # Capacity check — Eq (9)
            if load + cust.demand > inst.capacity:
                infeasible.append(cid)
                continue

            # Time-window check — Eq (10)-(14)
            start_service = max(arrival, cust.ready_time)
            if start_service > cust.due_date:
                infeasible.append(cid)
                continue

            # Check return-to-depot feasibility
            return_time = start_service + cust.service_time + inst.travel_time_matrix[cid][0]
            if return_time > depot.due_date:
                infeasible.append(cid)
                continue

            # Accept customer
            feasible.append(cid)
            load += cust.demand
            current_time = start_service + cust.service_time
            prev_id = cid

        return feasible, infeasible

    # ----- route metrics ----------------------------------------------------
    def route_details(self, route: List[int]):
        """
        Compute distance, waiting-times, and completion time for one route.

        Returns
        -------
        total_dist : float
        waiting_times : list[float]  (per customer in the route)
        completion_time : float      Tk
        """
        inst = self.inst
        total_dist = 0.0
        waiting_times: List[float] = []
        current_time = 0.0
        prev_id = 0

        for cid in route:
            cust = inst.customers[cid]
            d = inst.distance_matrix[prev_id][cid]
            total_dist += d
            travel = inst.travel_time_matrix[prev_id][cid]
            arrival = current_time + travel
            wait = max(0.0, cust.ready_time - arrival)
            waiting_times.append(wait)
            start_service = max(arrival, cust.ready_time)
            current_time = start_service + cust.service_time
            prev_id = cid

        # Return to depot
        total_dist += inst.distance_matrix[prev_id][0]
        completion_time = current_time + inst.travel_time_matrix[prev_id][0]

        return total_dist, waiting_times, completion_time
