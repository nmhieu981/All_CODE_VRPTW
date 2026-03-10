"""
Pareto Front Visualization
===========================
Fig. 9 style — 2D projections of 3-objective Pareto fronts.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional

import matplotlib.pyplot as plt
import numpy as np


def plot_pareto_2d(
    all_solutions: Dict[str, np.ndarray],
    instance_name: str,
    true_pf: Optional[np.ndarray] = None,
    save_dir: str = "results",
) -> None:
    """
    Plot 2D projections of Pareto fronts for multiple algorithms.

    Parameters
    ----------
    all_solutions : {algo_name: ndarray (N, 3)}
    """
    obj_labels = ["f1 (Distance)", "f2 (Wait Time)", "f3 (Imbalance)"]
    pairs = [(0, 1), (0, 2), (1, 2)]

    colors = {
        "iNSSSO": "#2196F3",
        "NSSSO": "#00BCD4",
        "SPEA2": "#4CAF50",
        "MOEA/D": "#FF9800",
        "NSGA-II": "#9C27B0",
        "MOPSO": "#F44336",
    }

    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    fig.suptitle(f"Pareto Front — {instance_name}", fontsize=14, fontweight="bold")

    for ax_idx, (i, j) in enumerate(pairs):
        ax = axes[ax_idx]
        for algo_name, objs in all_solutions.items():
            if len(objs) == 0:
                continue
            color = colors.get(algo_name, "#999999")
            ax.scatter(objs[:, i], objs[:, j], label=algo_name,
                       c=color, s=20, alpha=0.7)
        if true_pf is not None and len(true_pf) > 0:
            ax.scatter(true_pf[:, i], true_pf[:, j], label="True PF",
                       facecolors="none", edgecolors="red", s=60, linewidths=1.5)

        ax.set_xlabel(obj_labels[i])
        ax.set_ylabel(obj_labels[j])
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)

    plt.tight_layout()
    os.makedirs(save_dir, exist_ok=True)
    path = os.path.join(save_dir, f"pareto_{instance_name}.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()


def plot_pareto_3d(
    all_solutions: Dict[str, np.ndarray],
    instance_name: str,
    save_dir: str = "results",
) -> None:
    """3D scatter plot of Pareto fronts."""
    colors = {
        "iNSSSO": "#2196F3", "NSSSO": "#00BCD4", "SPEA2": "#4CAF50",
        "MOEA/D": "#FF9800", "NSGA-II": "#9C27B0", "MOPSO": "#F44336",
    }

    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection="3d")

    for algo_name, objs in all_solutions.items():
        if len(objs) == 0:
            continue
        color = colors.get(algo_name, "#999999")
        ax.scatter(objs[:, 0], objs[:, 1], objs[:, 2],
                   label=algo_name, c=color, s=20, alpha=0.7)

    ax.set_xlabel("f1 (Distance)")
    ax.set_ylabel("f2 (Wait Time)")
    ax.set_zlabel("f3 (Imbalance)")
    ax.set_title(f"3D Pareto Front — {instance_name}")
    ax.legend(fontsize=8)

    os.makedirs(save_dir, exist_ok=True)
    plt.savefig(os.path.join(save_dir, f"pareto3d_{instance_name}.png"),
                dpi=150, bbox_inches="tight")
    plt.close()
