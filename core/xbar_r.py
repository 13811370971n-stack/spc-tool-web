"""
Xbar-R Control Chart Engine.
Based on AIAG SPC Reference Manual.

Supports:
- Phase I (retrospective analysis): calculate limits from data
- Phase II (monitoring): use pre-calculated limits from Phase I
- 8 Western Electric out-of-control rules
- Process capability (Cp/Cpk/Pp/Ppk) with optional Box-Cox transform
"""

import numpy as np
import pandas as pd
from typing import Optional, List, Tuple, Dict, Any
from dataclasses import dataclass, field

from .constants import A2, D3, D4, D2, C4
from .control_rules import run_tests, get_all_violation_indices


@dataclass
class ControlLimits:
    """Control limits for a chart."""
    ucl: float
    cl: float
    lcl: float


@dataclass
class XbarRResult:
    """Complete Xbar-R analysis result."""
    # Subgroup statistics
    xbar: np.ndarray          # Subgroup means
    r: np.ndarray             # Subgroup ranges
    subgroup_size: int        # n

    # Xbar chart limits
    xbar_limits: ControlLimits
    # R chart limits
    r_limits: ControlLimits

    # Sigma estimates
    sigma_within: float       # Within-subgroup sigma (R-bar / d2)
    sigma_overall: float      # Overall sigma (pooled std)

    # Out-of-control test results
    xbar_violations: Dict[int, List[int]] = field(default_factory=dict)
    r_violations: Dict[int, List[int]] = field(default_factory=dict)

    # Capability (populated if spec limits provided)
    capability: Optional[Dict[str, float]] = None

    # Phase info
    phase: str = "I"          # "I" or "II"
    phase_1_limits: Optional[Dict[str, ControlLimits]] = None  # For Phase II reference

    # Metadata
    num_subgroups: int = 0
    excluded_subgroups: List[int] = field(default_factory=list)

    @property
    def xbar_in_control(self) -> bool:
        return len(self.xbar_violations) == 0

    @property
    def r_in_control(self) -> bool:
        return len(self.r_violations) == 0

    @property
    def in_control(self) -> bool:
        return self.xbar_in_control and self.r_in_control


def calculate_xbar_r(data: np.ndarray,
                     subgroup_size: Optional[int] = None,
                     enabled_tests: Optional[List[int]] = None,
                     usl: Optional[float] = None,
                     lsl: Optional[float] = None,
                     target: Optional[float] = None,
                     phase: str = "I",
                     phase_1_limits: Optional[Dict[str, ControlLimits]] = None,
                     exclude_subgroups: Optional[List[int]] = None) -> XbarRResult:
    """
    Calculate Xbar-R control chart statistics and limits.

    Parameters
    ----------
    data : np.ndarray
        2D array of shape (k, n) where k=subgroups, n=subgroup size.
        Or 1D array that will be reshaped using subgroup_size.
    subgroup_size : int, optional
        If data is 1D, reshape into subgroups of this size.
    enabled_tests : list of int, optional
        Which out-of-control tests to run (1-8). Default: [1,2,3,4].
    usl : float, optional
        Upper specification limit (for capability).
    lsl : float, optional
        Lower specification limit (for capability).
    target : float, optional
        Target value (for Cpm calculation).
    phase : str
        "I" for retrospective, "II" for monitoring with known limits.
    phase_1_limits : dict, optional
        Pre-calculated limits for Phase II. Keys: 'xbar', 'r' → ControlLimits.
    exclude_subgroups : list of int, optional
        Indices of subgroups to exclude from limit calculations (Phase I).

    Returns
    -------
    XbarRResult
        Complete analysis results.
    """
    # Default enabled tests: 1-4 (most common per AIAG)
    if enabled_tests is None:
        enabled_tests = [1, 2, 3, 4]

    # Reshape data if needed
    if data.ndim == 1:
        if subgroup_size is None or subgroup_size < 2:
            raise ValueError("subgroup_size must be ≥ 2 for Xbar-R chart. Use I-MR for n=1.")
        # Trim if not evenly divisible
        k = len(data) // subgroup_size
        data = data[:k * subgroup_size].reshape(k, subgroup_size)

    k, n = data.shape
    if n < 2:
        raise ValueError("Subgroup size must be ≥ 2 for Xbar-R chart. Use I-MR for n=1.")
    if n > 10:
        raise ValueError("Subgroup size > 10: use Xbar-S chart instead of Xbar-R.")

    # Calculate subgroup statistics
    xbar = np.nanmean(data, axis=1)
    r = np.nanmax(data, axis=1) - np.nanmin(data, axis=1)

    # Determine which subgroups to use for limit calculation
    if exclude_subgroups:
        mask = np.ones(k, dtype=bool)
        mask[exclude_subgroups] = False
    else:
        mask = np.ones(k, dtype=bool)

    if phase == "II" and phase_1_limits:
        # Use pre-calculated Phase I limits
        xbar_limits = phase_1_limits["xbar"]
        r_limits = phase_1_limits["r"]
    else:
        # Phase I: calculate from data
        x_double_bar = np.nanmean(xbar[mask])
        r_bar = np.nanmean(r[mask])

        # Xbar chart limits
        a2 = A2[n]
        xbar_ucl = x_double_bar + a2 * r_bar
        xbar_lcl = x_double_bar - a2 * r_bar
        xbar_limits = ControlLimits(ucl=xbar_ucl, cl=x_double_bar, lcl=xbar_lcl)

        # R chart limits
        d3 = D3[n]
        d4 = D4[n]
        r_ucl = d4 * r_bar
        r_lcl = d3 * r_bar
        r_limits = ControlLimits(ucl=r_ucl, cl=r_bar, lcl=r_lcl)

    # Sigma estimates
    r_bar_calc = np.nanmean(r[mask])
    d2 = D2[n]
    sigma_within = r_bar_calc / d2

    # Overall sigma (pooled standard deviation)
    all_data = data[mask].flatten()
    all_data = all_data[~np.isnan(all_data)]
    sigma_overall = np.std(all_data, ddof=1)

    # Run out-of-control tests
    xbar_violations = run_tests(xbar, xbar_limits.cl, xbar_limits.ucl, xbar_limits.lcl, enabled_tests)
    r_violations = run_tests(r, r_limits.cl, r_limits.ucl, r_limits.lcl, enabled_tests)

    # Process capability (if spec limits provided)
    capability = None
    if usl is not None or lsl is not None:
        capability = _calculate_capability(
            xbar_limits.cl, sigma_within, sigma_overall,
            usl=usl, lsl=lsl, target=target
        )

    return XbarRResult(
        xbar=xbar,
        r=r,
        subgroup_size=n,
        xbar_limits=xbar_limits,
        r_limits=r_limits,
        sigma_within=sigma_within,
        sigma_overall=sigma_overall,
        xbar_violations=xbar_violations,
        r_violations=r_violations,
        capability=capability,
        phase=phase,
        phase_1_limits=phase_1_limits,
        num_subgroups=k,
        excluded_subgroups=exclude_subgroups or [],
    )


def _calculate_capability(process_mean: float, sigma_within: float, sigma_overall: float,
                          usl: Optional[float] = None, lsl: Optional[float] = None,
                          target: Optional[float] = None) -> Dict[str, float]:
    """
    Calculate process capability indices.

    Within (short-term): Cp, Cpk, Cpu, Cpl
    Overall (long-term): Pp, Ppk, Ppu, Ppl
    Cpm (if target provided)
    """
    result = {}

    # Within capability (using sigma_within from R-bar/d2)
    if usl is not None and lsl is not None:
        result["Cp"] = (usl - lsl) / (6 * sigma_within)
    if usl is not None:
        result["Cpu"] = (usl - process_mean) / (3 * sigma_within)
    if lsl is not None:
        result["Cpl"] = (process_mean - lsl) / (3 * sigma_within)
    if "Cpu" in result and "Cpl" in result:
        result["Cpk"] = min(result["Cpu"], result["Cpl"])
    elif "Cpu" in result:
        result["Cpk"] = result["Cpu"]
    elif "Cpl" in result:
        result["Cpk"] = result["Cpl"]

    # Overall capability (using sigma_overall)
    if usl is not None and lsl is not None:
        result["Pp"] = (usl - lsl) / (6 * sigma_overall)
    if usl is not None:
        result["Ppu"] = (usl - process_mean) / (3 * sigma_overall)
    if lsl is not None:
        result["Ppl"] = (process_mean - lsl) / (3 * sigma_overall)
    if "Ppu" in result and "Ppl" in result:
        result["Ppk"] = min(result["Ppu"], result["Ppl"])
    elif "Ppu" in result:
        result["Ppk"] = result["Ppu"]
    elif "Ppl" in result:
        result["Ppk"] = result["Ppl"]

    # Cpm (Taguchi capability index)
    if target is not None and usl is not None and lsl is not None:
        sigma_t = np.sqrt(sigma_overall**2 + (process_mean - target)**2)
        result["Cpm"] = (usl - lsl) / (6 * sigma_t)

    return result


def summary_table(result: XbarRResult) -> pd.DataFrame:
    """
    Generate a summary statistics table for the Xbar-R analysis.
    """
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
            "Chart": "R (Range)",
            "UCL": f"{result.r_limits.ucl:.4f}",
            "CL": f"{result.r_limits.cl:.4f}",
            "LCL": f"{result.r_limits.lcl:.4f}",
            "In Control": "✓" if result.r_in_control else "✗",
            "Violations": str(list(result.r_violations.keys())) if result.r_violations else "None",
        },
    ]
    return pd.DataFrame(rows)
