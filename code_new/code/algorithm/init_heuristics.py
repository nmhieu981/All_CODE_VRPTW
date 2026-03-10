"""
Advanced Initialization & Local Search for VRPTW
=================================================
Clarke-Wright savings, multi-start, 2-opt*, cross-exchange, and
iterative local search to achieve near-optimal solutions.
"""

from __future__ import annotations

import math
import time
from typing import List, Tuple, Optional

import numpy as np

from core.problem import VRPTWInstance


# ===================================================================
#  Route evaluation helper (hot path — kept minimal)
# ===================================================================
def evaluate_route(route: List[int], inst: VRPTWInstance) -> Tuple[bool, float, float]:
    """Return (feasible, total_distance, completion_time)."""
    if not route:
        return True, 0.0, 0.0
    dm = inst.distance_matrix
    tm = inst.travel_time_matrix
    custs = inst.customers
    cap = inst.capacity
    depot_due = inst.depot.due_date
    t = 0.0
    load = 0.0
    dist = 0.0
    prev = 0
    for cid in route:
        c = custs[cid]
        if load + c.demand > cap:
            return False, float("inf"), 0
        dist += dm[prev][cid]
        arr = t + tm[prev][cid]
        start = max(arr, c.ready_time)
        if start > c.due_date:
            return False, float("inf"), 0
        fin = start + c.service_time
        if fin + tm[cid][0] > depot_due:
            return False, float("inf"), 0
        t = fin
        load += c.demand
        prev = cid
    dist += dm[prev][0]
    return True, dist, t + tm[prev][0]


def total_distance(routes: List[List[int]], inst: VRPTWInstance) -> float:
    s = 0.0
    for r in routes:
        _, d, _ = evaluate_route(r, inst)
        s += d
    return s


# ===================================================================
#  Clarke-Wright Savings Algorithm
# ===================================================================
def clarke_wright_savings(inst: VRPTWInstance) -> List[List[int]]:
    n = inst.n_customers
    routes: List[List[int]] = [[i] for i in range(1, n + 1)]
    routes = [r for r in routes if evaluate_route(r, inst)[0]]

    savings = []
    dm = inst.distance_matrix
    for i in range(1, n + 1):
        for j in range(i + 1, n + 1):
            s = dm[0][i] + dm[0][j] - dm[i][j]
            savings.append((s, i, j))
    savings.sort(reverse=True)

    cust_route = {}
    for ri, route in enumerate(routes):
        for cid in route:
            cust_route[cid] = ri

    for _, ci, cj in savings:
        ri = cust_route.get(ci)
        rj = cust_route.get(cj)
        if ri is None or rj is None or ri == rj:
            continue
        route_i = routes[ri]
        route_j = routes[rj]
        if not route_i or not route_j:
            continue

        candidates = []
        if route_i[-1] == ci and route_j[0] == cj:
            candidates.append(route_i + route_j)
        if route_j[-1] == cj and route_i[0] == ci:
            candidates.append(route_j + route_i)
        if route_i[-1] == ci and route_j[-1] == cj:
            candidates.append(route_i + route_j[::-1])
        if route_i[0] == ci and route_j[0] == cj:
            candidates.append(route_i[::-1] + route_j)

        for merged in candidates:
            ok, _, _ = evaluate_route(merged, inst)
            if ok:
                routes[ri] = merged
                routes[rj] = []
                for cid in merged:
                    cust_route[cid] = ri
                break

    return [r for r in routes if r]


# ===================================================================
#  Insertion Heuristic
# ===================================================================
def insertion_heuristic(inst: VRPTWInstance,
                        sort_key: str = "due_date") -> List[List[int]]:
    n = inst.n_customers
    sort_fns = {
        "due_date": lambda c: inst.customers[c].due_date,
        "ready_time": lambda c: inst.customers[c].ready_time,
        "demand": lambda c: -inst.customers[c].demand,
        "distance": lambda c: inst.distance_matrix[0][c],
        "angle": lambda c: math.atan2(
            inst.customers[c].y - inst.depot.y,
            inst.customers[c].x - inst.depot.x),
        "tw_center": lambda c: (inst.customers[c].ready_time +
                                 inst.customers[c].due_date) / 2,
    }
    customers = sorted(range(1, n + 1),
                       key=sort_fns.get(sort_key, sort_fns["due_date"]))
    routes: List[List[int]] = []

    for cid in customers:
        best_r = -1
        best_p = -1
        best_cost = float("inf")
        for ri, route in enumerate(routes):
            _, old_d, _ = evaluate_route(route, inst)
            for pos in range(len(route) + 1):
                cand = route[:pos] + [cid] + route[pos:]
                ok, d, _ = evaluate_route(cand, inst)
                if ok and d - old_d < best_cost:
                    best_cost = d - old_d
                    best_r = ri
                    best_p = pos
        if best_r >= 0:
            routes[best_r].insert(best_p, cid)
        else:
            routes.append([cid])
    return routes


# ===================================================================
#  Greedy Nearest Neighbour
# ===================================================================
def greedy_nearest_neighbour(inst: VRPTWInstance) -> List[List[int]]:
    unvisited = set(range(1, inst.n_customers + 1))
    routes: List[List[int]] = []
    dm = inst.distance_matrix
    tm = inst.travel_time_matrix
    custs = inst.customers
    cap = inst.capacity
    depot_due = inst.depot.due_date

    while unvisited:
        route: List[int] = []
        t = 0.0
        load = 0.0
        prev = 0
        while True:
            best_cid = -1
            best_score = float("inf")
            for cid in unvisited:
                c = custs[cid]
                if load + c.demand > cap:
                    continue
                arr = t + tm[prev][cid]
                start = max(arr, c.ready_time)
                if start > c.due_date:
                    continue
                if start + c.service_time + tm[cid][0] > depot_due:
                    continue
                score = start + dm[prev][cid] * 0.5
                if score < best_score:
                    best_score = score
                    best_cid = cid
            if best_cid < 0:
                break
            c = custs[best_cid]
            arr = t + tm[prev][best_cid]
            t = max(arr, c.ready_time) + c.service_time
            load += c.demand
            prev = best_cid
            route.append(best_cid)
            unvisited.discard(best_cid)
        if route:
            routes.append(route)
        else:
            break
    return routes


# ===================================================================
#  Intra-Route Local Search
# ===================================================================
def two_opt_route(route: List[int], inst: VRPTWInstance) -> List[int]:
    best = list(route)
    _, best_d, _ = evaluate_route(best, inst)
    improved = True
    while improved:
        improved = False
        for i in range(len(best) - 1):
            for j in range(i + 1, len(best)):
                cand = best[:i] + best[i:j+1][::-1] + best[j+1:]
                ok, d, _ = evaluate_route(cand, inst)
                if ok and d < best_d - 1e-10:
                    best = cand
                    best_d = d
                    improved = True
                    break
            if improved:
                break
    return best


def or_opt_route(route: List[int], inst: VRPTWInstance) -> List[int]:
    best = list(route)
    _, best_d, _ = evaluate_route(best, inst)
    improved = True
    while improved:
        improved = False
        for seg_len in [1, 2, 3]:
            for i in range(len(best) - seg_len + 1):
                seg = best[i:i+seg_len]
                rem = best[:i] + best[i+seg_len:]
                for j in range(len(rem) + 1):
                    cand = rem[:j] + seg + rem[j:]
                    ok, d, _ = evaluate_route(cand, inst)
                    if ok and d < best_d - 1e-10:
                        best = cand
                        best_d = d
                        improved = True
                        break
                if improved:
                    break
            if improved:
                break
    return best


# ===================================================================
#  Inter-Route Local Search (optimised)
# ===================================================================
def relocate_inter(routes: List[List[int]], inst: VRPTWInstance,
                   time_limit: float = 5.0) -> List[List[int]]:
    """Move one customer from one route to another."""
    routes = [list(r) for r in routes]
    start = time.time()
    improved = True
    while improved and time.time() - start < time_limit:
        improved = False
        old_total = total_distance(routes, inst)
        for si in range(len(routes)):
            if time.time() - start >= time_limit:
                break
            for cp in range(len(routes[si])):
                cid = routes[si][cp]
                src_w = routes[si][:cp] + routes[si][cp+1:]
                if src_w:
                    ok_s, ds, _ = evaluate_route(src_w, inst)
                    if not ok_s:
                        continue
                else:
                    ds = 0.0
                _, ds_old, _ = evaluate_route(routes[si], inst)
                gain_src = ds_old - ds

                for di in range(len(routes)):
                    if di == si:
                        continue
                    _, dd_old, _ = evaluate_route(routes[di], inst)
                    for ip in range(len(routes[di]) + 1):
                        new_dst = routes[di][:ip] + [cid] + routes[di][ip:]
                        ok, dd_new, _ = evaluate_route(new_dst, inst)
                        if ok and gain_src > dd_new - dd_old + 1e-10:
                            routes[si] = src_w
                            routes[di] = new_dst
                            routes = [r for r in routes if r]
                            improved = True
                            break
                    if improved:
                        break
                if improved:
                    break
            if improved:
                break
    return routes


def swap_inter(routes: List[List[int]], inst: VRPTWInstance,
               time_limit: float = 5.0) -> List[List[int]]:
    """Swap one customer between two routes."""
    routes = [list(r) for r in routes]
    start = time.time()
    improved = True
    while improved and time.time() - start < time_limit:
        improved = False
        for ri in range(len(routes)):
            if time.time() - start >= time_limit:
                break
            for rj in range(ri+1, len(routes)):
                old_di, old_dj = evaluate_route(routes[ri], inst)[1], evaluate_route(routes[rj], inst)[1]
                for pi in range(len(routes[ri])):
                    for pj in range(len(routes[rj])):
                        nri = list(routes[ri])
                        nrj = list(routes[rj])
                        nri[pi], nrj[pj] = nrj[pj], nri[pi]
                        ok_i, di, _ = evaluate_route(nri, inst)
                        if not ok_i:
                            continue
                        ok_j, dj, _ = evaluate_route(nrj, inst)
                        if ok_j and di + dj < old_di + old_dj - 1e-10:
                            routes[ri] = nri
                            routes[rj] = nrj
                            improved = True
                            break
                    if improved:
                        break
                if improved:
                    break
            if improved:
                break
    return routes


def cross_exchange(routes: List[List[int]], inst: VRPTWInstance,
                   time_limit: float = 5.0) -> List[List[int]]:
    """2-opt* (cross exchange): swap tails between two routes."""
    routes = [list(r) for r in routes]
    start = time.time()
    improved = True
    while improved and time.time() - start < time_limit:
        improved = False
        for ri in range(len(routes)):
            if time.time() - start >= time_limit:
                break
            for rj in range(ri+1, len(routes)):
                old_di = evaluate_route(routes[ri], inst)[1]
                old_dj = evaluate_route(routes[rj], inst)[1]
                for ki in range(len(routes[ri]) + 1):
                    if time.time() - start >= time_limit:
                        break
                    for lj in range(len(routes[rj]) + 1):
                        nri = routes[ri][:ki] + routes[rj][lj:]
                        nrj = routes[rj][:lj] + routes[ri][ki:]
                        if not nri or not nrj:
                            continue
                        ok_i, di, _ = evaluate_route(nri, inst)
                        if not ok_i:
                            continue
                        ok_j, dj, _ = evaluate_route(nrj, inst)
                        if ok_j and di + dj < old_di + old_dj - 1e-10:
                            routes[ri] = nri
                            routes[rj] = nrj
                            routes = [r for r in routes if r]
                            improved = True
                            break
                    if improved:
                        break
                if improved:
                    break
            if improved:
                break
    return routes


# ===================================================================
#  Ruin-and-Recreate
# ===================================================================
def ruin_and_recreate(routes: List[List[int]], inst: VRPTWInstance,
                      destroy_ratio: float = 0.3) -> List[List[int]]:
    """
    Remove a fraction of customers randomly, then re-insert them
    at the cheapest feasible positions (regret-based if possible).
    """
    all_customers = [c for r in routes for c in r]
    n_remove = max(1, int(len(all_customers) * destroy_ratio))

    # Random removal
    removed = list(np.random.choice(all_customers, size=n_remove, replace=False))
    removed_set = set(removed)

    # Build remaining routes
    remaining_routes = []
    for r in routes:
        new_r = [c for c in r if c not in removed_set]
        if new_r:
            remaining_routes.append(new_r)

    # Sort removed by due_date (tighter first)
    removed.sort(key=lambda c: inst.customers[c].due_date)

    # Greedy re-insertion at cheapest position
    for cid in removed:
        best_r = -1
        best_p = -1
        best_increase = float("inf")

        for ri, route in enumerate(remaining_routes):
            _, old_d, _ = evaluate_route(route, inst)
            for pos in range(len(route) + 1):
                cand = route[:pos] + [cid] + route[pos:]
                ok, d, _ = evaluate_route(cand, inst)
                if ok and d - old_d < best_increase:
                    best_increase = d - old_d
                    best_r = ri
                    best_p = pos

        if best_r >= 0:
            remaining_routes[best_r].insert(best_p, cid)
        else:
            remaining_routes.append([cid])

    return remaining_routes


def ruin_and_recreate_iter(routes: List[List[int]], inst: VRPTWInstance,
                           time_limit: float = 5.0,
                           n_iterations: int = 50) -> List[List[int]]:
    """Iterative ruin-and-recreate: keep best solution found."""
    best_routes = [list(r) for r in routes]
    best_dist = total_distance(best_routes, inst)
    start = time.time()

    for it in range(n_iterations):
        if time.time() - start >= time_limit:
            break

        # Vary destruction ratio
        ratio = np.random.uniform(0.15, 0.40)
        new_routes = ruin_and_recreate(best_routes, inst, destroy_ratio=ratio)

        # Quick 2-opt on affected routes
        new_routes = [two_opt_route(r, inst) for r in new_routes]
        new_routes = [r for r in new_routes if r]

        served = sum(len(r) for r in new_routes)
        if served == inst.n_customers:
            d = total_distance(new_routes, inst)
            if d < best_dist - 1e-10:
                best_dist = d
                best_routes = new_routes

    return best_routes


# ===================================================================
#  Route Merging — reduce number of vehicles
# ===================================================================
def merge_routes(routes: List[List[int]], inst: VRPTWInstance,
                 max_attempts: int = 5,
                 max_dist_increase: float = 0.05) -> List[List[int]]:
    """
    Try to merge short routes to reduce vehicle count.
    
    Strategy: Pick the shortest route, try to insert its customers
    into other routes. If all customers can be relocated → remove route.
    Repeat up to max_attempts times.
    
    Only accepts the merge if total distance does not increase by more
    than `max_dist_increase` (e.g., 0.05 = 5%).
    """
    routes = [list(r) for r in routes if r]
    
    for _ in range(max_attempts):
        if len(routes) <= 1:
            break
        
        # Sort by route length (customers), try to eliminate shortest
        route_lens = [(len(r), i) for i, r in enumerate(routes)]
        route_lens.sort()
        
        merged = False
        old_total_dist = total_distance(routes, inst)
        
        for _, short_idx in route_lens:
            if len(routes[short_idx]) == 0:
                continue
            
            short_route = routes[short_idx]
            # Try to insert all customers from short_route into other routes
            remaining = list(short_route)
            temp_routes = [list(r) for i, r in enumerate(routes) if i != short_idx]
            
            success = True
            for cid in remaining:
                # Find best insertion position across all other routes
                best_cost = float("inf")
                best_ri = -1
                best_pos = -1
                
                for ri, route in enumerate(temp_routes):
                    _, old_d, _ = evaluate_route(route, inst)
                    for pos in range(len(route) + 1):
                        cand = route[:pos] + [cid] + route[pos:]
                        ok, new_d, _ = evaluate_route(cand, inst)
                        if ok and new_d - old_d < best_cost:
                            best_cost = new_d - old_d
                            best_ri = ri
                            best_pos = pos
                
                if best_ri >= 0:
                    temp_routes[best_ri].insert(best_pos, cid)
                else:
                    success = False
                    break
            
            if success:
                # Verify distance penalty is acceptable
                temp_routes = [two_opt_route(r, inst) for r in temp_routes]
                new_total_dist = total_distance(temp_routes, inst)
                
                if new_total_dist <= old_total_dist * (1.0 + max_dist_increase):
                    routes = temp_routes
                    merged = True
                    break
        
        if not merged:
            break  # No more routes can be merged
    
    return routes



#  Full Local Search Pipeline
# ===================================================================
def full_local_search(routes: List[List[int]], inst: VRPTWInstance,
                      time_limit: float = 15.0) -> List[List[int]]:
    """Iterative local search with ruin-and-recreate."""
    start = time.time()
    remaining = lambda: max(0.1, time_limit - (time.time() - start))

    iteration = 0
    while time.time() - start < time_limit:
        iteration += 1
        old_dist = total_distance(routes, inst)

        # Intra-route
        routes = [two_opt_route(r, inst) for r in routes]
        routes = [or_opt_route(r, inst) for r in routes]

        # Inter-route
        rl = remaining() / 4
        routes = relocate_inter(routes, inst, time_limit=rl)
        routes = [r for r in routes if r]
        routes = swap_inter(routes, inst, time_limit=rl)
        routes = cross_exchange(routes, inst, time_limit=rl)
        routes = [r for r in routes if r]

        # Ruin-and-recreate (powerful diversification)
        routes = ruin_and_recreate_iter(routes, inst, time_limit=rl)

        # Post pass
        routes = [two_opt_route(r, inst) for r in routes]

        new_dist = total_distance(routes, inst)
        if new_dist >= old_dist - 0.5:
            break
    return routes


# ===================================================================
#  Multi-Start Best Initialization
# ===================================================================
def best_initialization(inst: VRPTWInstance,
                        time_limit: float = 10.0) -> List[List[int]]:
    """
    Phase 1: Generate candidates from multiple strategies (fast, no LS)
    Phase 2: Apply full LS to top-2, keep best.
    Phase 3: Extra ruin-and-recreate on the best result.
    """
    start = time.time()

    # Phase 1: Generate raw candidates quickly
    candidates: List[Tuple[str, List[List[int]], float]] = []

    for name, fn in [
        ("CW", lambda: clarke_wright_savings(inst)),
        ("NN", lambda: greedy_nearest_neighbour(inst)),
        ("INS-due", lambda: insertion_heuristic(inst, "due_date")),
        ("INS-ready", lambda: insertion_heuristic(inst, "ready_time")),
        ("INS-demand", lambda: insertion_heuristic(inst, "demand")),
        ("INS-dist", lambda: insertion_heuristic(inst, "distance")),
        ("INS-angle", lambda: insertion_heuristic(inst, "angle")),
        ("INS-tw", lambda: insertion_heuristic(inst, "tw_center")),
    ]:
        try:
            routes = fn()
            served = sum(len(r) for r in routes)
            if served == inst.n_customers:
                d = total_distance(routes, inst)
                candidates.append((name, routes, d))
        except Exception:
            pass

    if not candidates:
        return greedy_nearest_neighbour(inst)

    # Sort by distance, pick top-2
    candidates.sort(key=lambda x: x[2])
    top_k = candidates[:2]

    # Phase 2: Apply full LS to top-2
    used = time.time() - start
    remaining = max(2.0, time_limit - used)
    ls_time = remaining * 0.7 / len(top_k)  # 70% for LS phase

    best_routes = top_k[0][1]
    best_dist = top_k[0][2]

    for name, routes, raw_dist in top_k:
        if time.time() - start >= time_limit:
            break
        optimized = full_local_search(routes, inst, time_limit=ls_time)
        d = total_distance(optimized, inst)
        served = sum(len(r) for r in optimized)
        if served == inst.n_customers and d < best_dist:
            best_dist = d
            best_routes = optimized

    # Phase 3: Extra ruin-and-recreate on the best
    rr_time = max(0.5, time_limit - (time.time() - start))
    best_routes = ruin_and_recreate_iter(best_routes, inst,
                                         time_limit=rr_time, n_iterations=200)

    # Final 2-opt
    best_routes = [two_opt_route(r, inst) for r in best_routes]

    return best_routes
