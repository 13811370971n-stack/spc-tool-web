"""
Xbar-S Control Chart Engine.
Used when subgroup size n > 10 (where R chart becomes less efficient).
Based on AIAG SPC Reference Manual.

Uses A3, B3, B4, c4 constants instead of A2, D3, D4.
"""

import numpy as np
import pandas as pd
from typing import Optional, List, Dict
from dataclasses import dataclass, field

from .constants import A3, B3, B4, C4, D2
from .control_rules import run_tests, get_all_violation_indices
from .xbar_r import ControlLimits, _calculate_capability


@dataclass
class XbarSResult:
    """Complete Xbar-S analysis result."""
    # Subgroup statistics
    xbar: np.ndarray          # Subgroup means
    s: np.ndarray             # Subgroup standard deviations
    subgroup_size: int        # n

    # Xbar chart limits
    xbar_limits: ControlLimits
    # S chart limits
    s_limits: ControlLimits

    # Sigma estimates
    sigma_within: float       # Within-subgroup sigma (S-bar / c4)
    sigma_overall: float      # Overall sigma (pooled std)

    # Out-of-control test results
    xbar_violations: Dict[int, List[int]] = field(default_factory=dict)
    s_violations: Dict[int, List[int]] = field(default_factory=dict)

    # Capability
    capability: Optional[Dict[str, float]] = None

    # Phase info
    phase: str = "I"
    phase_1_limits: Optional[Dict[str, ControlLimits]] = None

    # Metadata
    num_subgroups: int = 0
    excluded_subgroups: List[int] = field(default_factory=list)

    @property
    def xbar_in_control(self) -> bool:
        return len(self.xbar_violations) == 0

    @property
    def s_in_control(self) -> bool:
        return len(self.s_violations) == 0

    @property
    def in_control(self) -> bool:
        return self.xbar_in_control and self.s_in_control


def calculate_xbar_s(data: np.ndarray,
                     subgroup_size: Optional[int] = None,
                     enabled_tests: Optional[List[int]] = None,
                     usl: Optional[float] = None,
                     lsl: Optional[float] = None,
                     target: Optional[float] = None,
                     phase: str = "I",
                     phase_1_limits: Optional[Dict[str, ControlLimits]] = None,
                     exclude_subgroups: Optional[List[int]] = None) -> XbarSResult:
    """
    Calculate Xbar-S control chart statistics and limits.

    Parameters
    ----------
    data : np.ndarray
        2D array (k, n) or 1D array to reshape.
    subgroup_size : int, optional
        If data is 1D, reshape using this size.
    enabled_tests : list of int, optional
        Which OOC tests to run (1-8). Default: [1,2,3,4].
    usl, lsl, target : float, optional
        Specification limits for capability analysis.
    phase : str
        "I" or "II".
    phase_1_limits : dict, optional
        Pre-calculated limits for Phase II.
    exclude_subgroups : list of int, optional
        Indices to exclude from limit calculation.

    Returns
    -------
    XbarSResult
    """
    if enabled_tests is None:
        enabled_tests = [1, 2, 3, 4]

    # Reshape if needed
    if data.ndim == 1:
        if subgroup_size is None or subgroup_size < 2:
            raise ValueError("subgroup_size must be >= 2 for Xbar-S chart.")
        k = len(data) // subgroup_size
        data = data[:k * subgroup_size].reshape(k, subgroup_size)

    k, n = data.shape
    if n < 2:
        raise ValueError("Subgroup size must be >= 2 for Xbar-S chart.")

    # Calculate subgroup statistics
    xbar = np.nanmean(data, axis=1)
    s = np.nanstd(data, axis=1, ddof=1)  # Sample std (n-1)

    # Mask for limit calculation
    if exclude_subgroups:
        mask = np.ones(k, dtype=bool)
        mask[exclude_subgroups] = False
    else:
        mask = np.ones(k, dtype=bool)

    if phase == "II" and phase_1_limits:
        xbar_limits = phase_1_limits["xbar"]
        s_limits = phase_1_limits["s"]
    else:
        # Phase I: calculate from data
        x_double_bar = np.nanmean(xbar[mask])
        s_bar = np.nanmean(s[mask])

        # Get constants (cap at n=25)
        n_const = min(n, 25)
        a3 = A3[n_const]
        b3 = B3[n_const]
        b4 = B4[n_const]

        # Xbar chart limits
        xbar_ucl = x_double_bar + a3 * s_bar
        xbar_lcl = x_double_bar - a3 * s_bar
        xbar_limits = ControlLimits(ucl=xbar_ucl, cl=x_double_bar, lcl=xbar_lcl)

        # S chart limits
        s_ucl = b4 * s_bar
        s_lcl = b3 * s_bar
        s_limits = ControlLimits(ucl=s_ucl, cl=s_bar, lcl=s_lcl)

    # Sigma estimates
    s_bar_calc = np.nanmean(s[mask])
    n_const = min(n, 25)
    c4 = C4[n_const]
    sigma_within = s_bar_calc / c4

    # Overall sigma
    all_data = data[mask].flatten()
    all_data = all_data[~np.isnan(all_data)]
    sigma_overall = np.std(all_data, ddof=1)

    # Run OOC tests
    xbar_violations = run_tests(xbar, xbar_limits.cl, xbar_limits.ucl, xbar_limits.lcl, enabled_tests)
    s_violations = run_tests(s, s_limits.cl, s_limits.ucl, s_limits.lcl, enabled_tests)

    # Capability
    capability = None
    if usl is not None or lsl is not None:
        capability = _calculate_capability(
            xbar_limits.cl, sigma_within, sigma_overall,
            usl=usl, lsl=lsl, target=target
        )

    return XbarSResult(
        xbar=xbar,
        s=s,
        subgroup_size=n,
        xbar_limits=xbar_limits,
        s_limits=s_limits,
        sigma_within=sigma_within,
        sigma_overall=sigma_overall,
        xbar_violations=xbar_violations,
        s_violations=s_violations,
        capability=capability,
        phase=phase,
        phase_1_limits=phase_1_limits,
        num_subgroups=k,
        excluded_subgroups=exclude_subgroups or [],
    )


def summary_table(result: XbarSResult) -> pd.DataFrame:
    """Generate summary statistics table."""
    rows = [
        {
            "Chart": "X̄ (Xbar)",
            "UCL": f"{result.xbar_limits.ucl:.4f}",
            "CL": f"{result.xbar_limits.cl:.4f}",
            "LCL": f"{result.xbar_limits.lcl:.4f}",
            "In Control": "✓" if result.xbar_in_control else "✗",
            "Violations": str(list(result.xbar_violations.keys())) if result.xbar_violations else "None",
        },
        {
            "Chart": "S (Std Dev)",
            "UCL": f"{result.s_limits.ucl:.4f}",
            "CL": f"{result.s_limits.cl:.4f}",
            "LCL": f"{result.s_limits.lcl:.4f}",
            "In Control": "✓" if result.s_in_control else "✗",
            "Violations": str(list(result.s_violations.keys())) if result.s_violations else "None",
        },
    ]
    return pd.DataFrame(rows)
