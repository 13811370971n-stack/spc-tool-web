"""
Z-MR (Standardized Individual-Moving Range) Control Chart Engine.
For short production runs with multiple part types.

Each part type has its own target and sigma. Data is standardized:
Z_i = (X_i - target_j) / sigma_j   where j is the part type

Then standard I-MR limits apply: UCL=+3, CL=0, LCL=-3 for Z chart.
"""

import numpy as np
import pandas as pd
from typing import Optional, List, Dict
from dataclasses import dataclass, field

from .constants import D4, D2
from .control_rules import run_tests
from .xbar_r import ControlLimits


@dataclass
class ZMRResult:
    """Complete Z-MR analysis result."""
    # Standardized values
    z: np.ndarray              # Standardized individual values
    z_mr: np.ndarray           # Moving ranges of Z values

    # Original data
    raw_data: np.ndarray       # Original X_i
    part_types: np.ndarray     # Part type labels

    # Per-type parameters
    type_params: Dict[str, Dict[str, float]]  # {type: {target, sigma}}

    # Z chart limits (fixed)
    z_limits: ControlLimits    # UCL=3, CL=0, LCL=-3
    # ZMR chart limits
    zmr_limits: ControlLimits

    # Violations
    z_violations: Dict[int, List[int]] = field(default_factory=dict)
    zmr_violations: Dict[int, List[int]] = field(default_factory=dict)

    # Metadata
    num_observations: int = 0
    num_types: int = 0

    @property
    def z_in_control(self) -> bool:
        return len(self.z_violations) == 0

    @property
    def zmr_in_control(self) -> bool:
        return len(self.zmr_violations) == 0

    @property
    def in_control(self) -> bool:
        return self.z_in_control and self.zmr_in_control


def calculate_zmr(data: np.ndarray,
                  part_types: np.ndarray,
                  targets: Optional[Dict[str, float]] = None,
                  sigmas: Optional[Dict[str, float]] = None,
                  enabled_tests: Optional[List[int]] = None) -> ZMRResult:
    """
    Calculate Z-MR control chart for short runs.

    Parameters
    ----------
    data : np.ndarray
        1D array of individual measurements.
    part_types : np.ndarray
        1D array of part type labels (same length as data).
    targets : dict, optional
        {part_type: target_value}. Defaults to per-type mean.
    sigmas : dict, optional
        {part_type: sigma_value}. Defaults to per-type MR-bar/d2 estimate.
    enabled_tests : list of int, optional
        Default: [1, 2, 3, 4].

    Returns
    -------
    ZMRResult
    """
    if enabled_tests is None:
        enabled_tests = [1, 2, 3, 4]

    data = np.asarray(data, dtype=float)
    part_types = np.asarray(part_types, dtype=str)
    n = len(data)

    if len(part_types) != n:
        raise ValueError("data and part_types must have same length.")

    unique_types = np.unique(part_types)

    # Calculate per-type parameters
    type_params = {}
    for ptype in unique_types:
        mask = part_types == ptype
        type_data = data[mask]

        # Target
        if targets and ptype in targets:
            t = targets[ptype]
        else:
            t = np.mean(type_data)

        # Sigma (MR-bar/d2 within each type)
        if sigmas and ptype in sigmas:
            s = sigmas[ptype]
        else:
            if len(type_data) >= 2:
                mr = np.abs(np.diff(type_data))
                s = np.mean(mr) / D2[2]
            else:
                s = 1.0  # Fallback

        type_params[ptype] = {"target": t, "sigma": s}

    # Standardize
    z = np.zeros(n)
    for i in range(n):
        ptype = part_types[i]
        t = type_params[ptype]["target"]
        s = type_params[ptype]["sigma"]
        z[i] = (data[i] - t) / s if s > 0 else 0.0

    # Moving range of Z
    z_mr = np.abs(np.diff(z))

    # Z chart limits (standard: ±3)
    z_limits = ControlLimits(ucl=3.0, cl=0.0, lcl=-3.0)

    # ZMR chart limits
    mr_bar = np.mean(z_mr)
    zmr_ucl = D4[2] * mr_bar  # D4(2) = 3.267
    zmr_limits = ControlLimits(ucl=zmr_ucl, cl=mr_bar, lcl=0.0)

    # Run OOC tests
    z_violations = run_tests(z, z_limits.cl, z_limits.ucl, z_limits.lcl, enabled_tests)
    zmr_violations = run_tests(z_mr, zmr_limits.cl, zmr_limits.ucl, zmr_limits.lcl, enabled_tests)

    return ZMRResult(
        z=z,
        z_mr=z_mr,
        raw_data=data,
        part_types=part_types,
        type_params=type_params,
        z_limits=z_limits,
        zmr_limits=zmr_limits,
        z_violations=z_violations,
        zmr_violations=zmr_violations,
        num_observations=n,
        num_types=len(unique_types),
    )


def summary_table(result: ZMRResult) -> pd.DataFrame:
    """Generate summary table."""
    rows = [
        {
            "Chart": "Z (Standardized)",
            "UCL": f"{result.z_limits.ucl:.1f}",
            "CL": f"{result.z_limits.cl:.1f}",
            "LCL": f"{result.z_limits.lcl:.1f}",
            "In Control": "✓" if result.z_in_control else "✗",
            "# Types": str(result.num_types),
        },
        {
            "Chart": "Z-MR",
            "UCL": f"{result.zmr_limits.ucl:.4f}",
            "CL": f"{result.zmr_limits.cl:.4f}",
            "LCL": f"{result.zmr_limits.lcl:.4f}",
            "In Control": "✓" if result.zmr_in_control else "✗",
            "# Types": "",
        },
    ]
    return pd.DataFrame(rows)
