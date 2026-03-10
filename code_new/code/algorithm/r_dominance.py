"""
R-Dominance Ranking for Preference-Based Optimization
======================================================
Vectorised implementation using NumPy for performance.

R-Dominance definition:
  x R-dominates y if:
    (1) x Pareto-dominates y, OR
    (2) x is in ROI and y is not, OR
    (3) both in ROI (or both outside), but ASF(x) < ASF(y)
"""

from __future__ import annotations

from typing import List, Tuple

import numpy as np

from core.preference import UserPreference
from algorithm.crowding import crowding_distance


def _compute_ideal_nadir(objectives: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Compute ideal (min per obj) and nadir (max per obj) from population."""
    return objectives.min(axis=0), objectives.max(axis=0)


def r_nondominated_sort(
    objectives: np.ndarray,
    pref: UserPreference,
) -> List[List[int]]:
    """
    R-Dominance based non-dominated sorting — vectorised.

    Uses precomputed ROI mask and ASF values with NumPy broadcasting
    for the dominance matrix, achieving ~10x speedup over scalar loops.
    """
    n = objectives.shape[0]
    if n == 0:
        return []

    ideal, nadir = _compute_ideal_nadir(objectives)

    # Precompute ROI and ASF for all solutions
    roi = pref.roi_mask(objectives, ideal, nadir)          # (N,) bool
    asf = pref.asf_augmented_batch(objectives)             # (N,) float

    # ── Vectorised R-dominance matrix (N, N) ──
    # Case 1: Pareto dominance via broadcasting
    a = objectives[:, np.newaxis, :]   # (N, 1, M)
    b = objectives[np.newaxis, :, :]   # (1, N, M)
    pareto_dom = (a <= b).all(axis=2) & (a < b).any(axis=2)  # (N, N)

    # Case 2: ROI membership — a in ROI, b not
    roi_a = roi[:, np.newaxis]         # (N, 1)
    roi_b = roi[np.newaxis, :]         # (1, N)
    roi_dom = roi_a & ~roi_b           # (N, N)

    # Case 3: Same ROI status + ASF comparison
    same_roi = (roi_a == roi_b)        # (N, N)
    asf_a = asf[:, np.newaxis]         # (N, 1)
    asf_b = asf[np.newaxis, :]         # (1, N)
    asf_dom = same_roi & (asf_a < asf_b - 1e-10)  # (N, N)

    # Combined: a R-dominates b if any case holds
    r_dom = pareto_dom | roi_dom | asf_dom  # (N, N)

    # Exclude self-dominance
    np.fill_diagonal(r_dom, False)

    # ── Front decomposition (same as fast_nondominated_sort) ──
    domination_count = r_dom.sum(axis=0).astype(int)  # how many R-dominate i
    dominated_set: List[List[int]] = [[] for _ in range(n)]
    for i in range(n):
        dominated_set[i] = np.where(r_dom[i])[0].tolist()

    current_front = np.where(domination_count == 0)[0].tolist()
    if not current_front:
        return [list(range(n))]

    fronts: List[List[int]] = [current_front]

    while fronts[-1]:
        next_front: List[int] = []
        for p in fronts[-1]:
            for q in dominated_set[p]:
                domination_count[q] -= 1
                if domination_count[q] == 0:
                    next_front.append(q)
        if next_front:
            fronts.append(next_front)
        else:
            break

    return fronts


def r_assign_rank_and_crowding(
    objectives: np.ndarray,
    pref: UserPreference,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    R-Dominance sorting + crowding distance computation.

    Returns
    -------
    ranks : ndarray shape (N,) — R-dominance rank per solution
    cds   : ndarray shape (N,) — crowding distance per solution
    """
    n = objectives.shape[0]
    ranks = np.full(n, n, dtype=int)
    cds = np.zeros(n)

    fronts = r_nondominated_sort(objectives, pref)

    for rank, front in enumerate(fronts):
        for idx in front:
            ranks[idx] = rank
        cd_vals = crowding_distance(objectives, front, normalize=True)
        for i, idx in enumerate(front):
            cds[idx] = cd_vals[i]

    return ranks, cds


def select_best_r(
    objectives: np.ndarray,
    n_select: int,
    pref: UserPreference,
) -> List[int]:
    """
    Select best solutions using R-dominance rank + ASF tie-breaking.

    Primary: R-rank (ascending)
    Secondary: ASF score (ascending — closer to preference)
    Tertiary: crowding distance (descending — diversity)
    """
    n = objectives.shape[0]
    ranks, cds = r_assign_rank_and_crowding(objectives, pref)
    asf_vals = pref.asf_augmented_batch(objectives)

    indices = list(range(n))
    indices.sort(key=lambda i: (ranks[i], asf_vals[i], -cds[i]))
    return indices[:n_select]


def select_gbest_asf(
    population_objectives: np.ndarray,
    pref: UserPreference,
    candidate_indices: List[int],
    route_counts: np.ndarray = None,
) -> int:
    """
    Select gBest by minimising ASF via binary tournament.
    If route_counts is provided, fewer routes is strictly preferred.
    """
    n = len(candidate_indices)
    if n == 0:
        return 0
    if n == 1:
        return candidate_indices[0]

    # Binary tournament
    i1, i2 = np.random.choice(n, size=2, replace=False)
    idx1 = candidate_indices[i1]
    idx2 = candidate_indices[i2]

    # Hierarchical priority: n_routes first
    if route_counts is not None:
        c1 = route_counts[idx1]
        c2 = route_counts[idx2]
        if c1 < c2:
            return idx1
        elif c2 < c1:
            return idx2

    asf1 = pref.asf_augmented(population_objectives[idx1])
    asf2 = pref.asf_augmented(population_objectives[idx2])

    return idx1 if asf1 <= asf2 else idx2
