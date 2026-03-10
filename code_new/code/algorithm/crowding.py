"""
Crowding Distance & Selection — Enhanced
==========================================
Normalized crowding distance, duplicate elimination, and improved selection.
Based on Section 2.3 / Table 2 of Lai et al., Applied Soft Computing 2025.
"""

from __future__ import annotations

from typing import List

import numpy as np

from algorithm.nondominated import fast_nondominated_sort


# ─── Epsilon tolerance for detecting duplicate objectives ──────────
_EPS_DUP = 1e-6


def crowding_distance(objectives: np.ndarray, front_indices: List[int],
                      normalize: bool = True) -> np.ndarray:
    """
    Compute crowding distance for solutions in a single front.

    Parameters
    ----------
    objectives : (N, M)  full objective matrix
    front_indices : indices of solutions in this front
    normalize : if True, normalize each objective to [0,1] before computing CD

    Returns
    -------
    cd : ndarray of len(front_indices)  — crowding distances
    """
    n_front = len(front_indices)
    if n_front <= 2:
        return np.full(n_front, np.inf)

    n_obj = objectives.shape[1]
    front_obj = objectives[front_indices].copy()

    # Normalize each objective to [0,1] to avoid scale bias
    if normalize:
        for m in range(n_obj):
            f_min = front_obj[:, m].min()
            f_max = front_obj[:, m].max()
            rng = f_max - f_min
            if rng > 0:
                front_obj[:, m] = (front_obj[:, m] - f_min) / rng

    cd = np.zeros(n_front)

    for m in range(n_obj):
        sorted_idx = np.argsort(front_obj[:, m])
        cd[sorted_idx[0]] = np.inf
        cd[sorted_idx[-1]] = np.inf

        f_min = front_obj[sorted_idx[0], m]
        f_max = front_obj[sorted_idx[-1], m]
        denom = f_max - f_min
        if denom == 0:
            continue

        for i in range(1, n_front - 1):
            cd[sorted_idx[i]] += (
                (front_obj[sorted_idx[i + 1], m] - front_obj[sorted_idx[i - 1], m])
                / denom
            )

    return cd


def assign_rank_and_crowding(
    objectives: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Perform non-dominated sorting then compute normalized crowding distances.

    Returns
    -------
    ranks : ndarray shape (N,)
    cds   : ndarray shape (N,)
    """
    n = objectives.shape[0]
    ranks = np.full(n, n, dtype=int)  # default high rank
    cds = np.zeros(n)

    fronts = fast_nondominated_sort(objectives)
    for rank, front in enumerate(fronts):
        for idx in front:
            ranks[idx] = rank
        cd_vals = crowding_distance(objectives, front, normalize=True)
        for i, idx in enumerate(front):
            cds[idx] = cd_vals[i]

    return ranks, cds


def _find_unique_indices(objectives: np.ndarray, eps: float = _EPS_DUP) -> List[int]:
    """Return indices of unique solutions (remove duplicates within eps)."""
    n = objectives.shape[0]
    if n == 0:
        return []

    unique = [0]
    for i in range(1, n):
        is_dup = False
        for j in unique:
            if np.all(np.abs(objectives[i] - objectives[j]) < eps):
                is_dup = True
                break
        if not is_dup:
            unique.append(i)

    return unique


def select_best(
    objectives: np.ndarray,
    n_select: int,
    route_counts: np.ndarray = None,
) -> List[int]:
    """
    Select the best *n_select* solutions by rank then crowding distance.
    
    When route_counts is provided, vehicle count is the PRIMARY criterion:
    fewer routes always beats more routes (hierarchical/lexicographic).
    
    Sort order: (n_routes, duplicate_flag, rank, -crowding_distance)
    """
    n = objectives.shape[0]
    ranks, cds = assign_rank_and_crowding(objectives)

    # Detect duplicates — mark them with a penalty
    unique_set = set(_find_unique_indices(objectives))
    is_dup = np.array([0 if i in unique_set else 1 for i in range(n)])

    indices = list(range(n))
    if route_counts is not None:
        # Hierarchical: n_routes first, then rank, then CD
        indices.sort(key=lambda i: (route_counts[i], is_dup[i], ranks[i], -cds[i]))
    else:
        indices.sort(key=lambda i: (is_dup[i], ranks[i], -cds[i]))
    return indices[:n_select]


def select_gbest(
    pareto_indices: List[int],
    crowding_dists: np.ndarray,
    route_counts: np.ndarray = None,
) -> int:
    """
    Choose gbest from Pareto front via binary tournament on crowding distance.
    If route_counts is provided, fewer routes is strictly preferred.
    """
    n = len(pareto_indices)
    if n <= 1:
        return pareto_indices[0] if n == 1 else 0

    # Binary tournament: pick 2 random
    i1, i2 = np.random.choice(n, size=2, replace=False)
    idx1 = pareto_indices[i1]
    idx2 = pareto_indices[i2]
    
    cd1 = crowding_dists[i1]
    cd2 = crowding_dists[i2]

    # Hierarchical priority: n_routes first
    if route_counts is not None:
        c1 = route_counts[idx1]
        c2 = route_counts[idx2]
        if c1 < c2:
            return idx1
        elif c2 < c1:
            return idx2

    # Tie-break with crowding distance
    if np.isinf(cd1) and np.isinf(cd2):
        chosen = np.random.choice([i1, i2])
    elif np.isinf(cd1):
        chosen = i1
    elif np.isinf(cd2):
        chosen = i2
    else:
        chosen = i1 if cd1 >= cd2 else i2

    return pareto_indices[chosen]
