"""
Route Visualizer
================
Plot vehicle routes on a 2D plane with customer locations.
"""

from __future__ import annotations

import os
from typing import List, Optional

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

from core.problem import VRPTWInstance
from core.solution import Solution


# Distinct colours for routes
_ROUTE_COLORS = [
    "#E53935", "#1E88E5", "#43A047", "#FB8C00", "#8E24AA",
    "#00ACC1", "#FFB300", "#5E35B1", "#3949AB", "#D81B60",
    "#00897B", "#7CB342", "#C0CA33", "#F4511E", "#6D4C41",
    "#546E7A", "#EC407A", "#AB47BC", "#42A5F5", "#26A69A",
]


def plot_routes(
    solution: Solution,
    instance: VRPTWInstance,
    title: Optional[str] = None,
    save_dir: str = "results",
    filename: Optional[str] = None,
) -> None:
    """
    Plot the routes of a solution on the customer coordinate plane.

    Features:
    - Depot marked with a red star
    - Each route in a distinct colour with arrows
    - Customer IDs labelled
    """
    fig, ax = plt.subplots(figsize=(12, 10))

    depot = instance.depot
    ax.plot(depot.x, depot.y, "r*", markersize=18, zorder=5, label="Depot")

    routes = solution.routes if solution.routes else []

    for r_idx, route in enumerate(routes):
        color = _ROUTE_COLORS[r_idx % len(_ROUTE_COLORS)]
        prev_x, prev_y = depot.x, depot.y

        for cid in route:
            cust = instance.customers[cid]
            ax.annotate(
                "",
                xy=(cust.x, cust.y),
                xytext=(prev_x, prev_y),
                arrowprops=dict(arrowstyle="->", color=color, lw=1.5),
            )
            ax.plot(cust.x, cust.y, "o", color=color, markersize=6, zorder=4)
            ax.annotate(str(cid), (cust.x + 0.5, cust.y + 0.5),
                        fontsize=6, color=color)
            prev_x, prev_y = cust.x, cust.y

        # Return to depot
        ax.annotate(
            "",
            xy=(depot.x, depot.y),
            xytext=(prev_x, prev_y),
            arrowprops=dict(arrowstyle="->", color=color, lw=1.5, alpha=0.5),
        )

    # Legend
    patches = [
        mpatches.Patch(color=_ROUTE_COLORS[i % len(_ROUTE_COLORS)],
                       label=f"Route {i+1} ({len(r)} cust)")
        for i, r in enumerate(routes)
    ]
    ax.legend(handles=patches, fontsize=7, loc="upper right", ncol=2)

    t = title or f"Routes — {instance.name}"
    ax.set_title(t, fontsize=14, fontweight="bold")
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.grid(True, alpha=0.2)

    os.makedirs(save_dir, exist_ok=True)
    fn = filename or f"routes_{instance.name}.png"
    plt.savefig(os.path.join(save_dir, fn), dpi=150, bbox_inches="tight")
    plt.close()
