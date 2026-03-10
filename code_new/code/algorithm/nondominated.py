"""
Fast Non-dominated Sorting — Vectorised
=========================================
Optimised implementation using NumPy broadcasting.
Based on Section 2.3 / Table 2 of Lai et al., Applied Soft Computing 2025.
"""

from __future__ import annotations

from typing import List

import numpy as np


def dominates_vec(objectives: np.ndarray) -> np.ndarray:
    """
    Vectorised pairwise dominance check.

    Returns
    -------
    dom_matrix : bool ndarray (N, N)
        dom_matrix[i, j] = True  ⟺  solution i dominates solution j.
    """
    N = objectives.shape[0]
    # (N, 1, M) vs (1, N, M)  →  (N, N, M)
    a = objectives[:, np.newaxis, :]
    b = objectives[np.newaxis, :, :]

    leq = a <= b            # ∀m: f_m(a) ≤ f_m(b)
    lt  = a < b             # ∃m: f_m(a) < f_m(b)

    all_leq = leq.all(axis=2)           # (N, N)
    any_lt  = lt.any(axis=2)            # (N, N)

    return all_leq & any_lt             # (N, N)


def fast_nondominated_sort(objectives: np.ndarray) -> List[List[int]]:
    """
    Deb's fast non-dominated sort — vectorised O(M·N²) with NumPy.

    Parameters
    ----------
    objectives : ndarray of shape (N, M)
        N solutions, M objectives (all minimised).

    Returns
    -------
    fronts : list[list[int]]
        fronts[0] = Pareto front (rank 0), fronts[1] = rank 1, …
    """
    n = objectives.shape[0]
    if n == 0:
        return []

    dom = dominates_vec(objectives)      # (N, N) bool

    # domination_count[i] = how many solutions dominate i
    domination_count = dom.sum(axis=0).astype(int)   # col-sum

    # dominated_set[i] = set of solutions dominated by i
    dominated_set: List[List[int]] = [[] for _ in range(n)]
    for i in range(n):
        dominated_set[i] = np.where(dom[i])[0].tolist()

    fronts: List[List[int]] = []
    current_front = np.where(domination_count == 0)[0].tolist()
    if not current_front:
        # Fallback: all solutions as front 0
        return [list(range(n))]

    fronts.append(current_front)

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


def is_dominated_by_set(point: np.ndarray, ref_set: np.ndarray) -> bool:
    """Check if a single point is dominated by any member of ref_set."""
    if ref_set.shape[0] == 0:
        return False
    leq = ref_set <= point
    lt  = ref_set < point
    return bool(np.any(leq.all(axis=1) & lt.any(axis=1)))


def dominates(obj_a, obj_b) -> bool:
    """
    Backward-compatible scalar dominance check.
    Return True if *a* dominates *b* (all objectives minimised).
    """
    a = np.asarray(obj_a)
    b = np.asarray(obj_b)
    return bool(np.all(a <= b) and np.any(a < b))
