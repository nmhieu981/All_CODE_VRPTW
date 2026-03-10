"""
VRPTW Problem Definition
========================
Loads Solomon benchmark instances (CSV / TXT format) and builds distance matrix.

References
----------
Section 3 of Lai et al., Applied Soft Computing 2025.
"""

from __future__ import annotations

import csv
import math
import os
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np


@dataclass
class Customer:
    """Single customer (or depot when id == 0)."""
    id: int
    x: float
    y: float
    demand: float
    ready_time: float   # earliest service start (tE_i)
    due_date: float     # latest service start   (tL_i)
    service_time: float


@dataclass
class VRPTWInstance:
    """Complete VRPTW problem instance."""
    name: str
    n_vehicles: int
    capacity: float
    customers: List[Customer]          # index-0 = depot
    distance_matrix: np.ndarray = field(repr=False, default=None)
    travel_time_matrix: np.ndarray = field(repr=False, default=None)

    # Derived -----------------------------------------------------------------
    @property
    def n_customers(self) -> int:
        """Number of customers *excluding* the depot."""
        return len(self.customers) - 1

    @property
    def depot(self) -> Customer:
        return self.customers[0]

    # Construction helpers ----------------------------------------------------
    def build_matrices(self, speed: float = 1.0) -> None:
        """Build Euclidean distance and travel-time matrices."""
        n = len(self.customers)
        self.distance_matrix = np.zeros((n, n))
        for i in range(n):
            for j in range(i + 1, n):
                dx = self.customers[i].x - self.customers[j].x
                dy = self.customers[i].y - self.customers[j].y
                d = math.sqrt(dx * dx + dy * dy)
                self.distance_matrix[i][j] = d
                self.distance_matrix[j][i] = d
        self.travel_time_matrix = self.distance_matrix / speed

    # I/O ---------------------------------------------------------------------
    @classmethod
    def load_csv(cls, filepath: str) -> "VRPTWInstance":
        """
        Load a Solomon instance from CSV format.

        Expected CSV header:
            CUST NO.,XCOORD.,YCOORD.,DEMAND,READY TIME,DUE DATE,SERVICE TIME
        Row 0 is the depot (CUST NO. = 1, demand = 0).
        """
        customers: List[Customer] = []
        name = os.path.splitext(os.path.basename(filepath))[0]

        with open(filepath, "r", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                cust = Customer(
                    id=len(customers),  # re-index from 0
                    x=float(row["XCOORD."]),
                    y=float(row["YCOORD."]),
                    demand=float(row["DEMAND"]),
                    ready_time=float(row["READY TIME"]),
                    due_date=float(row["DUE DATE"]),
                    service_time=float(row["SERVICE TIME"]),
                )
                customers.append(cust)

        # CSV files don't carry vehicle info → use Solomon default
        n_vehicles, capacity = _solomon_defaults(name)

        inst = cls(
            name=name,
            n_vehicles=n_vehicles,
            capacity=capacity,
            customers=customers,
        )
        inst.build_matrices()
        return inst

    @classmethod
    def load_txt(cls, filepath: str) -> "VRPTWInstance":
        """
        Load a Solomon instance from the standard TXT format.

        Format:
            Line 1  : instance name
            Lines 3-4: VEHICLE / NUMBER CAPACITY header + values
            Line 7  : CUSTOMER header
            Line 9+ : customer data rows
        """
        customers: List[Customer] = []

        with open(filepath, "r") as fh:
            lines = fh.readlines()

        name = lines[0].strip()

        # Parse vehicle info (line index 4)
        veh_parts = lines[4].split()
        n_vehicles = int(veh_parts[0])
        capacity = float(veh_parts[1])

        # Parse customer data (starts at line 9)
        for line in lines[9:]:
            parts = line.split()
            if not parts:
                continue
            cust = Customer(
                id=int(parts[0]),
                x=float(parts[1]),
                y=float(parts[2]),
                demand=float(parts[3]),
                ready_time=float(parts[4]),
                due_date=float(parts[5]),
                service_time=float(parts[6]),
            )
            customers.append(cust)

        inst = cls(
            name=name,
            n_vehicles=n_vehicles,
            capacity=capacity,
            customers=customers,
        )
        inst.build_matrices()
        return inst

    @classmethod
    def load(cls, filepath: str) -> "VRPTWInstance":
        """Auto-detect format and load."""
        ext = os.path.splitext(filepath)[1].lower()
        if ext == ".csv":
            return cls.load_csv(filepath)
        return cls.load_txt(filepath)


def _solomon_defaults(name: str):
    """Return (n_vehicles, capacity) for well-known Solomon groups."""
    upper = name.upper()
    if upper.startswith("C1"):
        return 25, 200
    elif upper.startswith("C2"):
        return 25, 700
    elif upper.startswith("R1"):
        return 25, 200
    elif upper.startswith("R2"):
        return 25, 1000
    elif upper.startswith("RC1"):
        return 25, 200
    elif upper.startswith("RC2"):
        return 25, 1000
    else:
        return 25, 200


def find_solomon_instances(data_dir: str, fmt: str = "csv") -> List[str]:
    """Return sorted list of absolute paths for Solomon benchmark files."""
    paths: List[str] = []
    for root, _dirs, files in os.walk(data_dir):
        for f in files:
            if f.lower().endswith(f".{fmt}"):
                paths.append(os.path.join(root, f))
    paths.sort()
    return paths
