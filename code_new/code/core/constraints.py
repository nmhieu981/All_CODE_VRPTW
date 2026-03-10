"""
Constraints Module
==================
Capacity and time-window constraint utilities (Equations 6, 9–14).
"""

from __future__ import annotations

from typing import List, Tuple

from core.problem import VRPTWInstance


def check_capacity(route: List[int], instance: VRPTWInstance) -> bool:
    """Eq (9): total demand ≤ vehicle capacity."""
    total = sum(instance.customers[cid].demand for cid in route)
    return total <= instance.capacity


def check_time_windows(route: List[int], instance: VRPTWInstance) -> Tuple[bool, List[int]]:
    """
    Eq (10)–(14): check time-window feasibility for every customer.

    Returns
    -------
    feasible : bool
    violators : list[int]   Customer ids that violate.
    """
    depot = instance.depot
    violators: List[int] = []
    current_time = 0.0
    prev_id = 0

    for cid in route:
        cust = instance.customers[cid]
        travel = instance.travel_time_matrix[prev_id][cid]
        arrival = current_time + travel
        start_service = max(arrival, cust.ready_time)

        if start_service > cust.due_date:
            violators.append(cid)
            continue

        # Check return to depot
        return_time = start_service + cust.service_time + instance.travel_time_matrix[cid][0]
        if return_time > depot.due_date:
            violators.append(cid)
            continue

        current_time = start_service + cust.service_time
        prev_id = cid

    return len(violators) == 0, violators


def route_load(route: List[int], instance: VRPTWInstance) -> float:
    """Total demand along a route."""
    return sum(instance.customers[cid].demand for cid in route)
