"""
I-MR (Individual - Moving Range) Control Chart Engine.
Used when subgroup size n=1 (individual measurements).
Based on AIAG SPC Reference Manual.

Sigma estimated from MR-bar / d2(2) = MR-bar / 1.128
"""

import numpy as np
import pandas as pd
from typing import Optional, List, Dict
from dataclasses import dataclass, field

from .constants import D2, D4, E2
from .control_rules import run_tests, get_all_violation_indices
from .xbar_r import ControlLimits, _calculate_capability


@dataclass
class IMRResult:
    """Complete I-MR analysis result."""
    # Individual values and moving ranges
    individuals: np.ndarray    # Individual values (X)
    mr: np.ndarray             # Moving ranges (|X_i - X_{i-1}|)
    mr_span: int               # Moving range span (default 2)

    # I chart limits
    i_limits: ControlLimits
    # MR chart limits
    mr_limits: ControlLimits

    # Sigma estimates
    sigma_within: float        # MR-bar / d2
    sigma_overall: float       # Overall std

    # Out-of-control test results
    i_violations: Dict[int, List[int]] = field(default_factory=dict)
    mr_violations: Dict[int, List[int]] = field(default_factory=dict)

    # Capability
    capability: Optional[Dict[str, float]] = None

    # Phase info
    phase: str = "I"
    phase_1_limits: Optional[Dict[str, ControlLimits]] = None

    # Metadata
    num_observations: int = 0
    excluded_points: List[int] = field(default_factory=list)

    @property
    def i_in_control(self) -> bool:
        return len(self.i_violations) == 0

    @property
    def mr_in_control(self) -> bool:
        return len(self.mr_violations) == 0

    @property
    def in_control(self) -> bool:
        return self.i_in_control and self.mr_in_control


def calculate_imr(data: np.ndarray,
                  mr_span: int = 2,
                  enabled_tests: Optional[List[int]] = None,
                  usl: Optional[float] = None,
                  lsl: Optional[float] = None,
                  target: Optional[float] = None,
                  phase: str = "I",
                  phase_1_limits: Optional[Dict[str, ControlLimits]] = None,
                  exclude_points: Optional[List[int]] = None) -> IMRResult:
    """
    Calculate I-MR control chart statistics and limits.

    Parameters
    ----------
    data : np.ndarray
        1D array of individual measurements.
    mr_span : int
        Moving range span (default 2 = consecutive differences).
    enabled_tests : list of int, optional
        Which OOC tests to run. Default: [1,2,3,4].
    usl, lsl, target : float, optional
        Specification limits for capability.
    phase : str
        "I" or "II".
    phase_1_limits : dict, optional
        Pre-calculated limits for Phase II.
    exclude_points : list of int, optional
        Indices to exclude from limit calculations.

    Returns
    -------
    IMRResult
    """
    if enabled_tests is None:
        enabled_tests = [1, 2, 3, 4]

    # Flatten if needed
    data = np.asarray(data, dtype=float).flatten()
    data = data[~np.isnan(data)]
    n = len(data)

    if n < 3:
        raise ValueError("Need at least 3 observations for I-MR chart.")

    # Calculate moving ranges
    mr = np.abs(np.diff(data, n=1))  # |X_i - X_{i-1}|

    # For span > 2, use max of span consecutive differences
    if mr_span > 2:
        mr_extended = []
        for i in range(len(data) - mr_span + 1):
            segment = data[i:i + mr_span]
            mr_extended.append(np.max(segment) - np.min(segment))
        mr = np.array(mr_extended)

    # Mask for exclusion
    if exclude_points:
        mask_i = np.ones(n, dtype=bool)
        mask_i[exclude_points] = False
        # MR mask: exclude if either endpoint is excluded
        mask_mr = np.ones(len(mr), dtype=bool)
        for idx in exclude_points:
            if idx > 0 and idx - 1 < len(mask_mr):
                mask_mr[idx - 1] = False
            if idx < len(mask_mr):
                mask_mr[idx] = False
    else:
        mask_i = np.ones(n, dtype=bool)
        mask_mr = np.ones(len(mr), dtype=bool)

    if phase == "II" and phase_1_limits:
        i_limits = phase_1_limits["i"]
        mr_limits = phase_1_limits["mr"]
    else:
        # Phase I: calculate from data
        x_bar = np.mean(data[mask_i])
        mr_bar = np.mean(mr[mask_mr])

        # I chart limits: X-bar ± E2 * MR-bar  (E2 = 3/d2(2) = 2.66)
        # Or equivalently: X-bar ± 3 * (MR-bar / d2(2))
        d2 = D2[2]  # d2 for n=2 (moving range of span 2)
        sigma_mr = mr_bar / d2

        i_ucl = x_bar + 3 * sigma_mr
        i_lcl = x_bar - 3 * sigma_mr
        i_limits = ControlLimits(ucl=i_ucl, cl=x_bar, lcl=i_lcl)

        # MR chart limits
        d4 = D4[2]  # D4 for n=2 = 3.267
        mr_ucl = d4 * mr_bar
        mr_lcl = 0.0  # D3 for n=2 = 0
        mr_limits = ControlLimits(ucl=mr_ucl, cl=mr_bar, lcl=mr_lcl)

    # Sigma estimates
    mr_bar_calc = np.mean(mr[mask_mr])
    d2 = D2[2]
    sigma_within = mr_bar_calc / d2
    sigma_overall = np.std(data[mask_i], ddof=1)

    # Run OOC tests
    i_violations = run_tests(data, i_limits.cl, i_limits.ucl, i_limits.lcl, enabled_tests)
    mr_violations = run_tests(mr, mr_limits.cl, mr_limits.ucl, mr_limits.lcl, enabled_tests)

    # Capability
    capability = None
    if usl is not None or lsl is not None:
        capability = _calculate_capability(
            i_limits.cl, sigma_within, sigma_overall,
            usl=usl, lsl=lsl, target=target
        )

    return IMRResult(
        individuals=data,
        mr=mr,
        mr_span=mr_span,
        i_limits=i_limits,
        mr_limits=mr_limits,
        sigma_within=sigma_within,
        sigma_overall=sigma_overall,
        i_violations=i_violations,
        mr_violations=mr_violations,
        capability=capability,
        phase=phase,
        phase_1_limits=phase_1_limits,
        num_observations=n,
        excluded_points=exclude_points or [],
    )


def summary_table(result: IMRResult) -> pd.DataFrame:
    """Generate summary statistics table."""
    rows = [
        {
            "Chart": "I (Individual)",
            "UCL": f"{result.i_limits.ucl:.4f}",
            "CL": f"{result.i_limits.cl:.4f}",
            "LCL": f"{result.i_limits.lcl:.4f}",
            "In Control": "✓" if result.i_in_control else "✗",
            "Violations": str(list(result.i_violations.keys())) if result.i_violations else "None",
        },
        {
            "Chart": "MR (Moving Range)",
            "UCL": f"{result.mr_limits.ucl:.4f}",
            "CL": f"{result.mr_limits.cl:.4f}",
            "LCL": f"{result.mr_limits.lcl:.4f}",
            "In Control": "✓" if result.mr_in_control else "✗",
            "Violations": str(list(result.mr_violations.keys())) if result.mr_violations else "None",
        },
    ]
    return pd.DataFrame(rows)
