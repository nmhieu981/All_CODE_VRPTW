"""
Convergence Plot
================
Fig. 8 style — Mean IGD over time with log-scale y-axis.
"""

from __future__ import annotations

import os
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import numpy as np


def plot_convergence(
    convergence_data: Dict[str, List[List[Tuple[float, float]]]],
    instance_name: str,
    save_dir: str = "results",
) -> None:
    """
    Plot convergence curves for multiple algorithms.

    Parameters
    ----------
    convergence_data : {algo_name: list of runs, each run = [(time, igd_proxy)]}
    """
    colors = {
        "iNSSSO": "#2196F3", "NSSSO": "#00BCD4", "SPEA2": "#4CAF50",
        "MOEA/D": "#FF9800", "NSGA-II": "#9C27B0", "MOPSO": "#F44336",
    }

    fig, ax = plt.subplots(figsize=(10, 6))

    for algo_name, all_runs in convergence_data.items():
        # Average across runs at common time points
        if not all_runs or not all_runs[0]:
            continue

        # Interpolate to common time grid
        max_time = max(run[-1][0] for run in all_runs if run)
        t_grid = np.linspace(0, max_time, 200)
        igd_matrix = []

        for run_conv in all_runs:
            if not run_conv:
                continue
            times = np.array([t for t, _ in run_conv])
            vals = np.array([v for _, v in run_conv])
            interp = np.interp(t_grid, times, vals)
            igd_matrix.append(interp)

        if not igd_matrix:
            continue

        mean_igd = np.mean(igd_matrix, axis=0)
        color = colors.get(algo_name, "#999999")
        ax.semilogy(t_grid, mean_igd, label=algo_name, color=color, linewidth=2)

    ax.set_xlabel("Time (seconds)", fontsize=12)
    ax.set_ylabel("Mean IGD Proxy (Log Scale)", fontsize=12)
    ax.set_title(f"Convergence — {instance_name}", fontsize=14, fontweight="bold")
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)

    os.makedirs(save_dir, exist_ok=True)
    plt.savefig(os.path.join(save_dir, f"convergence_{instance_name}.png"),
                dpi=150, bbox_inches="tight")
    plt.close()


def plot_convergence_multi(
    convergence_data: Dict[str, Dict[str, List[List[Tuple[float, float]]]]],
    instance_names: List[str],
    save_dir: str = "results",
) -> None:
    """
    Multi-subplot convergence plot (e.g. 4 instances like Fig. 8).

    convergence_data[instance][algo] = list of run convergences
    """
    n = len(instance_names)
    cols = min(n, 2)
    rows = (n + cols - 1) // cols

    fig, axes = plt.subplots(rows, cols, figsize=(8 * cols, 5 * rows))
    if n == 1:
        axes = [axes]
    else:
        axes = axes.flat

    colors = {
        "iNSSSO": "#2196F3", "NSSSO": "#00BCD4", "SPEA2": "#4CAF50",
        "MOEA/D": "#FF9800", "NSGA-II": "#9C27B0", "MOPSO": "#F44336",
    }

    for idx, inst_name in enumerate(instance_names):
        ax = axes[idx]
        inst_data = convergence_data.get(inst_name, {})

        for algo_name, all_runs in inst_data.items():
            if not all_runs or not all_runs[0]:
                continue
            max_time = max(run[-1][0] for run in all_runs if run)
            t_grid = np.linspace(0, max_time, 200)
            igd_matrix = []
            for run_conv in all_runs:
                if not run_conv:
                    continue
                times = np.array([t for t, _ in run_conv])
                vals = np.array([v for _, v in run_conv])
                interp = np.interp(t_grid, times, vals)
                igd_matrix.append(interp)
            if not igd_matrix:
                continue
            mean_igd = np.mean(igd_matrix, axis=0)
            color = colors.get(algo_name, "#999999")
            ax.semilogy(t_grid, mean_igd, label=algo_name, color=color, linewidth=2)

        ax.set_title(inst_name, fontsize=12, fontweight="bold")
        ax.set_xlabel("Seconds")
        ax.set_ylabel("Mean IGD (Log)")
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)

    plt.tight_layout()
    os.makedirs(save_dir, exist_ok=True)
    plt.savefig(os.path.join(save_dir, "convergence_multi.png"),
                dpi=150, bbox_inches="tight")
    plt.close()
