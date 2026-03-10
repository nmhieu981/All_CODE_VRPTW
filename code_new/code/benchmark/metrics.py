"""
Performance Metrics
===================
Section 5.1, Equations 19–21 of Lai et al., Applied Soft Computing 2025.

* Coverage  (Cov)
* Inverted Generational Distance  (IGD)
* Hypervolume  (HV)
* Reference-based Hypervolume  (R-HV)
* Number of nondominated solutions  (Nnds)
* Best ASF score
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np

from algorithm.nondominated import dominates, fast_nondominated_sort


class PerformanceMetrics:
    """Compute quality indicators including preference-based metrics."""

    # ----- Coverage  (Eq 19) ------------------------------------------------
    @staticmethod
    def coverage(p_approx: np.ndarray, p_true: np.ndarray) -> float:
        """
        Cov(P_approx, P_true) =
            |{v ∈ P_true : ∃ v' ∈ P_approx,  v' dominates or equals v}|
            / |P_true|
        """
        if len(p_true) == 0:
            return 0.0

        count = 0
        for v in p_true:
            for vp in p_approx:
                if np.all(vp <= v):   # dominates or equals
                    count += 1
                    break
        return count / len(p_true)

    # ----- Inverted Generational Distance  (Eq 20) -------------------------
    @staticmethod
    def igd(p_approx: np.ndarray, p_true: np.ndarray) -> float:
        """
        IGD = (1/|P_true|) Σ min_dist(v, P_approx)
        Objectives normalised by max values in P_true.
        """
        if len(p_true) == 0 or len(p_approx) == 0:
            return float("inf")

        # Normalise
        max_vals = p_true.max(axis=0)
        max_vals[max_vals == 0] = 1.0
        pt_norm = p_true / max_vals
        pa_norm = p_approx / max_vals

        total = 0.0
        for v in pt_norm:
            dists = np.linalg.norm(pa_norm - v, axis=1)
            total += dists.min()

        return total / len(p_true)

    # ----- Hypervolume  (Eq 21) --------------------------------------------
    @staticmethod
    def hypervolume(p_approx: np.ndarray,
                    reference_point: Optional[np.ndarray] = None) -> float:
        """
        Hypervolume indicator.
        Uses pymoo's HV implementation for 3-objective problems.
        """
        if len(p_approx) == 0:
            return 0.0

        # Normalise to [0, 1]
        max_vals = p_approx.max(axis=0)
        max_vals[max_vals == 0] = 1.0
        normed = p_approx / max_vals

        if reference_point is None:
            reference_point = np.array([1.1] * p_approx.shape[1])

        try:
            from pymoo.indicators.hv import HV
            indicator = HV(ref_point=reference_point)
            return float(indicator(normed))
        except ImportError:
            # Fallback: Monte-Carlo estimate
            return _mc_hypervolume(normed, reference_point, n_samples=100_000)

    # ----- R-HV  (Reference-based Hypervolume) ------------------------------
    @staticmethod
    def r_hypervolume(p_approx: np.ndarray,
                      pref=None) -> float:
        """
        Reference-based Hypervolume: HV computed only for solutions
        within the Region of Interest (ROI) around the reference point g.

        Uses the nadir of ROI solutions as the reference bound,
        measuring how well the ROI region is covered.
        """
        if len(p_approx) == 0 or pref is None:
            return 0.0

        ideal = p_approx.min(axis=0)
        nadir = p_approx.max(axis=0)

        # Filter to ROI solutions
        roi_mask = pref.roi_mask(p_approx, ideal, nadir)
        roi_objs = p_approx[roi_mask]

        if len(roi_objs) == 0:
            return 0.0

        # Normalise ROI solutions to [0,1] using their own min/max
        roi_min = roi_objs.min(axis=0)
        roi_max = roi_objs.max(axis=0)
        ranges = roi_max - roi_min
        ranges = np.where(ranges < 1e-10, 1.0, ranges)

        normed = (roi_objs - roi_min) / ranges
        normed = np.clip(normed, 0.0, 1.0)

        ref_normed = np.ones(roi_objs.shape[1]) * 1.1

        try:
            from pymoo.indicators.hv import HV
            indicator = HV(ref_point=ref_normed)
            return float(indicator(normed))
        except ImportError:
            return _mc_hypervolume(normed, ref_normed, n_samples=50_000)

    # ----- Best ASF ---------------------------------------------------------
    @staticmethod
    def best_asf(p_approx: np.ndarray, pref=None) -> float:
        """Best (minimum) ASF score in the approximation set."""
        if len(p_approx) == 0 or pref is None:
            return float("inf")
        asf_vals = pref.asf_batch(p_approx)
        return float(np.min(asf_vals))

    # ----- ROI count --------------------------------------------------------
    @staticmethod
    def roi_count(p_approx: np.ndarray, pref=None) -> int:
        """Number of solutions within the Region of Interest."""
        if len(p_approx) == 0 or pref is None:
            return 0
        ideal = p_approx.min(axis=0)
        nadir = p_approx.max(axis=0)
        return int(pref.roi_mask(p_approx, ideal, nadir).sum())

    # ----- Nnds -------------------------------------------------------------
    @staticmethod
    def nnds(p_approx: np.ndarray) -> int:
        """Number of nondominated solutions."""
        if len(p_approx) == 0:
            return 0
        fronts = fast_nondominated_sort(p_approx)
        return len(fronts[0]) if fronts else 0

    # ----- True Pareto estimation -------------------------------------------
    @staticmethod
    def estimate_true_pareto(all_solutions: np.ndarray) -> np.ndarray:
        """
        Aggregate solutions from all algorithms/runs, return the
        nondominated front as the estimated true Pareto set.
        """
        if len(all_solutions) == 0:
            return np.empty((0, 3))
        fronts = fast_nondominated_sort(all_solutions)
        return all_solutions[fronts[0]]

    # ----- Convenience: compute all at once --------------------------------
    def compute_all(
        self,
        p_approx: np.ndarray,
        p_true: np.ndarray,
        pref=None,
    ) -> Dict[str, float]:
        result = {
            "Cov": self.coverage(p_approx, p_true),
            "IGD": self.igd(p_approx, p_true),
            "HV": self.hypervolume(p_approx),
            "Nnds": float(self.nnds(p_approx)),
        }
        if pref is not None:
            result["R-HV"] = self.r_hypervolume(p_approx, pref)
            result["Best_ASF"] = self.best_asf(p_approx, pref)
            result["ROI_Count"] = float(self.roi_count(p_approx, pref))
        return result

    # ----- Aggregate over multiple runs ------------------------------------
    @staticmethod
    def aggregate(run_metrics: List[Dict[str, float]]) -> Dict[str, Tuple[float, float]]:
        """Return (mean, std) for each metric over multiple runs."""
        agg: Dict[str, Tuple[float, float]] = {}
        all_keys = set()
        for m in run_metrics:
            all_keys.update(m.keys())
        for key in all_keys:
            vals = [m[key] for m in run_metrics if key in m]
            if vals:
                agg[key] = (float(np.mean(vals)), float(np.std(vals)))
        return agg


# ---------------------------------------------------------------------------
# Fallback Monte-Carlo HV estimate
# ---------------------------------------------------------------------------
def _mc_hypervolume(points: np.ndarray, ref: np.ndarray,
                    n_samples: int = 100_000) -> float:
    n_obj = points.shape[1]
    lower = points.min(axis=0)
    vol_box = float(np.prod(ref - lower))
    samples = np.random.uniform(lower, ref, (n_samples, n_obj))
    dominated_count = 0
    for s in samples:
        for p in points:
            if np.all(p <= s):
                dominated_count += 1
                break
    return vol_box * dominated_count / n_samples

