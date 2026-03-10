"""
User Preference for Preference-Based Multi-Objective Optimization
==================================================================
Reference Point (g), Weight Vector (w), Achievement Scalarizing Function (ASF),
and Region of Interest (ROI) for R-Dominance based search.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple

import numpy as np


@dataclass
class UserPreference:
    """
    User-defined preference structure for guiding MO optimization.

    Parameters
    ----------
    g : array-like, shape (M,)
        Reference/aspiration point — the desired objective values.
        e.g. [828.0, 0.0, 0.12] for (distance, wait_time, imbalance).
    w : array-like, shape (M,)
        Weight vector — importance of each objective (should sum to 1).
        e.g. [0.5, 0.3, 0.2] — distance most important.
    delta : float
        ROI (Region of Interest) radius factor.
        Controls the size of the preferred region around g.
    """

    g: np.ndarray
    w: np.ndarray
    delta: float = 0.1

    def __post_init__(self):
        self.g = np.asarray(self.g, dtype=float)
        self.w = np.asarray(self.w, dtype=float)
        # Normalise weights to sum to 1
        w_sum = self.w.sum()
        if w_sum > 0:
            self.w = self.w / w_sum

    @property
    def n_obj(self) -> int:
        return len(self.g)

    # ─── Achievement Scalarizing Function (ASF) ────────────────────────
    def asf(self, obj: np.ndarray) -> float:
        """
        ASF(x, g, w) = max_{i=1..M} { w_i * (f_i(x) - g_i) }

        Measures the worst weighted deviation from the reference point.
        Lower is better — solution closer to g in all weighted dimensions.
        """
        obj = np.asarray(obj, dtype=float)
        deviations = self.w * (obj - self.g)
        return float(np.max(deviations))

    def asf_augmented(self, obj: np.ndarray, rho: float = 1e-3) -> float:
        """
        Augmented ASF with tie-breaking sum term:
        ASF_aug = max_i{w_i*(f_i-g_i)} + ρ * Σ w_i*(f_i-g_i)

        Ensures strict ordering even when max terms are tied.
        """
        obj = np.asarray(obj, dtype=float)
        deviations = self.w * (obj - self.g)
        return float(np.max(deviations) + rho * np.sum(deviations))

    # ─── Weighted distance from reference point ────────────────────────
    def weighted_distance(self, obj: np.ndarray) -> float:
        """Weighted Euclidean distance from g."""
        obj = np.asarray(obj, dtype=float)
        diff = self.w * (obj - self.g)
        return float(np.sqrt(np.sum(diff ** 2)))

    # ─── Region of Interest (ROI) ──────────────────────────────────────
    def in_roi(self, obj: np.ndarray,
               ideal: np.ndarray, nadir: np.ndarray) -> bool:
        """
        Check if a solution falls within the Region of Interest.

        ROI is defined as the hyper-ellipsoid around g:
            Σ (w_i * (f_i - g_i) / (delta * (nadir_i - ideal_i)))^2 ≤ 1

        Parameters
        ----------
        obj : objective vector of the solution
        ideal : ideal point (best known per objective)
        nadir : nadir point (worst in Pareto front per objective)
        """
        obj = np.asarray(obj, dtype=float)
        ideal = np.asarray(ideal, dtype=float)
        nadir = np.asarray(nadir, dtype=float)

        ranges = nadir - ideal
        ranges = np.where(ranges < 1e-10, 1.0, ranges)  # avoid div-by-zero

        normalised_dist = self.w * (obj - self.g) / (self.delta * ranges)
        return float(np.sum(normalised_dist ** 2)) <= 1.0

    # ─── Batch operations ──────────────────────────────────────────────
    def asf_batch(self, objectives: np.ndarray) -> np.ndarray:
        """Compute ASF for an array of solutions (N, M) → (N,)."""
        deviations = self.w[np.newaxis, :] * (objectives - self.g[np.newaxis, :])
        return np.max(deviations, axis=1)

    def asf_augmented_batch(self, objectives: np.ndarray,
                            rho: float = 1e-3) -> np.ndarray:
        """Compute augmented ASF for array of solutions (N, M) → (N,)."""
        deviations = self.w[np.newaxis, :] * (objectives - self.g[np.newaxis, :])
        return np.max(deviations, axis=1) + rho * np.sum(deviations, axis=1)

    def roi_mask(self, objectives: np.ndarray,
                 ideal: np.ndarray, nadir: np.ndarray) -> np.ndarray:
        """Return boolean mask (N,) — True if solution is in ROI."""
        ranges = nadir - ideal
        ranges = np.where(ranges < 1e-10, 1.0, ranges)

        norm_dist = (self.w[np.newaxis, :] *
                     (objectives - self.g[np.newaxis, :]) /
                     (self.delta * ranges[np.newaxis, :]))
        return np.sum(norm_dist ** 2, axis=1) <= 1.0
