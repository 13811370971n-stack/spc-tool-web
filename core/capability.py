"""
Process Capability Analysis Module.
Comprehensive capability study with:
- Normal capability (Cp, Cpk, Pp, Ppk, Cpm)
- Box-Cox transformation for non-normal data
- Johnson transformation
- Normality testing (Anderson-Darling, Shapiro-Wilk)
- Within vs Overall comparison
- Histogram + fitted distribution overlay

Based on AIAG SPC Reference Manual (2026 Edition).
"""

import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import minimize_scalar
from typing import Optional, Dict, Tuple
from dataclasses import dataclass, field


@dataclass
class NormalityResult:
    """Normality test results."""
    # Anderson-Darling
    ad_statistic: float
    ad_critical_values: list
    ad_significance_levels: list
    ad_is_normal: bool  # at α=0.05

    # Shapiro-Wilk
    sw_statistic: float
    sw_p_value: float
    sw_is_normal: bool  # p > 0.05

    @property
    def is_normal(self) -> bool:
        """Normal if both tests agree."""
        return self.ad_is_normal and self.sw_is_normal


@dataclass
class CapabilityResult:
    """Complete process capability analysis result."""
    # Data info
    n: int
    mean: float
    std_overall: float
    std_within: float

    # Normality
    normality: NormalityResult

    # Within (short-term) capability
    cp: Optional[float] = None
    cpk: Optional[float] = None
    cpu: Optional[float] = None
    cpl: Optional[float] = None

    # Overall (long-term) capability
    pp: Optional[float] = None
    ppk: Optional[float] = None
    ppu: Optional[float] = None
    ppl: Optional[float] = None

    # Taguchi
    cpm: Optional[float] = None

    # Spec limits used
    usl: Optional[float] = None
    lsl: Optional[float] = None
    target: Optional[float] = None

    # Expected defect rate (PPM)
    ppm_within: Optional[float] = None
    ppm_overall: Optional[float] = None

    # Transformation (if applied)
    transformation: Optional[str] = None  # "None", "Box-Cox", "Johnson"
    lambda_boxcox: Optional[float] = None
    transformed_data: Optional[np.ndarray] = None

    # Subgroup info
    subgroup_size: Optional[int] = None
    num_subgroups: Optional[int] = None


def test_normality(data: np.ndarray) -> NormalityResult:
    """
    Test normality using Anderson-Darling and Shapiro-Wilk.

    Parameters
    ----------
    data : np.ndarray
        1D array of observations.

    Returns
    -------
    NormalityResult
    """
    data = data[~np.isnan(data)]

    # Anderson-Darling test
    ad_result = stats.anderson(data, dist='norm')
    # Check at 5% significance level (index 2 in the result)
    ad_is_normal = ad_result.statistic < ad_result.critical_values[2]

    # Shapiro-Wilk test (limited to n ≤ 5000)
    if len(data) > 5000:
        sw_data = np.random.choice(data, 5000, replace=False)
    else:
        sw_data = data
    sw_stat, sw_p = stats.shapiro(sw_data)
    sw_is_normal = sw_p > 0.05

    return NormalityResult(
        ad_statistic=ad_result.statistic,
        ad_critical_values=list(ad_result.critical_values),
        ad_significance_levels=list(ad_result.significance_level),
        ad_is_normal=ad_is_normal,
        sw_statistic=sw_stat,
        sw_p_value=sw_p,
        sw_is_normal=sw_is_normal,
    )


def boxcox_transform(data: np.ndarray, lambda_: Optional[float] = None) -> Tuple[np.ndarray, float]:
    """
    Apply Box-Cox transformation.

    Parameters
    ----------
    data : np.ndarray
        Must be strictly positive (data > 0).
    lambda_ : float, optional
        Transformation parameter. If None, finds optimal lambda.

    Returns
    -------
    (transformed_data, lambda_used)
    """
    data = data[~np.isnan(data)]

    if np.any(data <= 0):
        # Shift data to make positive
        shift = abs(np.min(data)) + 1.0
        data = data + shift
    else:
        shift = 0.0

    if lambda_ is None:
        # Find optimal lambda
        transformed, best_lambda = stats.boxcox(data)
    else:
        best_lambda = lambda_
        if lambda_ == 0:
            transformed = np.log(data)
        else:
            transformed = (data**lambda_ - 1) / lambda_

    return transformed, best_lambda


def calculate_capability(data: np.ndarray,
                         usl: Optional[float] = None,
                         lsl: Optional[float] = None,
                         target: Optional[float] = None,
                         subgroup_size: Optional[int] = None,
                         subgroup_data: Optional[np.ndarray] = None,
                         transform: str = "none") -> CapabilityResult:
    """
    Perform comprehensive process capability analysis.

    Parameters
    ----------
    data : np.ndarray
        1D array of all individual measurements.
    usl : float, optional
        Upper specification limit.
    lsl : float, optional
        Lower specification limit.
    target : float, optional
        Target value. Defaults to midpoint of spec limits.
    subgroup_size : int, optional
        If provided, estimates within-subgroup sigma from R-bar/d2 or S-bar/c4.
    subgroup_data : np.ndarray, optional
        2D array (k x n) of subgrouped data for within-sigma estimation.
    transform : str
        "none", "boxcox", or "johnson". Default "none".

    Returns
    -------
    CapabilityResult
    """
    data = np.asarray(data, dtype=float).flatten()
    data = data[~np.isnan(data)]
    n = len(data)

    if n < 2:
        raise ValueError("Need at least 2 observations.")

    # Apply transformation if requested
    transformation_name = "None"
    lambda_bc = None
    transformed = None

    if transform == "boxcox":
        transformed, lambda_bc = boxcox_transform(data)
        transformation_name = "Box-Cox"
        analysis_data = transformed
    elif transform == "johnson":
        # Johnson transformation using scipy
        # Try SU family first
        try:
            gamma, delta, xi, lam = stats.johnsonsu.fit(data)
            transformed = stats.johnsonsu.ppf(stats.johnsonsu.cdf(data, gamma, delta, xi, lam), 0, 1)
            transformation_name = "Johnson SU"
        except Exception:
            transformed = data
            transformation_name = "Johnson (failed, using raw)"
        analysis_data = transformed
    else:
        analysis_data = data

    # Normality test
    normality = test_normality(analysis_data)

    # Process mean and std
    process_mean = np.mean(analysis_data)
    std_overall = np.std(analysis_data, ddof=1)

    # Within-subgroup sigma estimation
    if subgroup_data is not None and subgroup_data.ndim == 2:
        k_sg, n_sg = subgroup_data.shape
        from .constants import D2, C4
        if n_sg <= 10:
            # Use R-bar / d2
            ranges = np.nanmax(subgroup_data, axis=1) - np.nanmin(subgroup_data, axis=1)
            r_bar = np.mean(ranges)
            std_within = r_bar / D2[n_sg]
        else:
            # Use S-bar / c4
            s_vals = np.nanstd(subgroup_data, axis=1, ddof=1)
            s_bar = np.mean(s_vals)
            n_c4 = min(n_sg, 25)
            std_within = s_bar / C4[n_c4]
        num_subgroups = k_sg
        sg_size = n_sg
    elif subgroup_size and subgroup_size > 1:
        # Estimate from MR of subgroup means
        k_sg = n // subgroup_size
        reshaped = analysis_data[:k_sg * subgroup_size].reshape(k_sg, subgroup_size)
        from .constants import D2, C4
        if subgroup_size <= 10:
            ranges = np.max(reshaped, axis=1) - np.min(reshaped, axis=1)
            r_bar = np.mean(ranges)
            std_within = r_bar / D2[subgroup_size]
        else:
            s_vals = np.std(reshaped, axis=1, ddof=1)
            s_bar = np.mean(s_vals)
            n_c4 = min(subgroup_size, 25)
            std_within = s_bar / C4[n_c4]
        num_subgroups = k_sg
        sg_size = subgroup_size
    else:
        # Individual data: use MR-bar/d2 (moving range method)
        mr = np.abs(np.diff(analysis_data))
        mr_bar = np.mean(mr)
        from .constants import D2
        std_within = mr_bar / D2[2]
        num_subgroups = None
        sg_size = 1

    # Default target to midpoint
    if target is None and usl is not None and lsl is not None:
        target = (usl + lsl) / 2.0

    # Calculate capability indices
    cp = cpk = cpu = cpl = pp = ppk = ppu = ppl = cpm = None
    ppm_within = ppm_overall = None

    if usl is not None and lsl is not None:
        cp = (usl - lsl) / (6 * std_within)
        pp = (usl - lsl) / (6 * std_overall)

    if usl is not None:
        cpu = (usl - process_mean) / (3 * std_within)
        ppu = (usl - process_mean) / (3 * std_overall)

    if lsl is not None:
        cpl = (process_mean - lsl) / (3 * std_within)
        ppl = (process_mean - lsl) / (3 * std_overall)

    if cpu is not None and cpl is not None:
        cpk = min(cpu, cpl)
    elif cpu is not None:
        cpk = cpu
    elif cpl is not None:
        cpk = cpl

    if ppu is not None and ppl is not None:
        ppk = min(ppu, ppl)
    elif ppu is not None:
        ppk = ppu
    elif ppl is not None:
        ppk = ppl

    # Cpm (Taguchi)
    if target is not None and usl is not None and lsl is not None:
        sigma_t = np.sqrt(std_overall**2 + (process_mean - target)**2)
        cpm = (usl - lsl) / (6 * sigma_t)

    # Expected PPM outside spec
    if usl is not None and lsl is not None:
        # Within (short-term)
        z_upper_w = (usl - process_mean) / std_within
        z_lower_w = (process_mean - lsl) / std_within
        ppm_within = (stats.norm.sf(z_upper_w) + stats.norm.sf(z_lower_w)) * 1e6

        # Overall (long-term)
        z_upper_o = (usl - process_mean) / std_overall
        z_lower_o = (process_mean - lsl) / std_overall
        ppm_overall = (stats.norm.sf(z_upper_o) + stats.norm.sf(z_lower_o)) * 1e6

    return CapabilityResult(
        n=n,
        mean=process_mean,
        std_overall=std_overall,
        std_within=std_within,
        normality=normality,
        cp=cp, cpk=cpk, cpu=cpu, cpl=cpl,
        pp=pp, ppk=ppk, ppu=ppu, ppl=ppl,
        cpm=cpm,
        usl=usl, lsl=lsl, target=target,
        ppm_within=ppm_within, ppm_overall=ppm_overall,
        transformation=transformation_name,
        lambda_boxcox=lambda_bc,
        transformed_data=transformed,
        subgroup_size=sg_size,
        num_subgroups=num_subgroups,
    )


def summary_table(result: CapabilityResult) -> pd.DataFrame:
    """Generate capability summary table."""
    rows = []

    if result.cp is not None:
        rows.append({"Index": "Cp", "Within": f"{result.cp:.4f}", "Overall": f"{result.pp:.4f}" if result.pp else "N/A"})
    if result.cpk is not None:
        rows.append({"Index": "Cpk", "Within": f"{result.cpk:.4f}", "Overall": f"{result.ppk:.4f}" if result.ppk else "N/A"})
    if result.cpu is not None:
        rows.append({"Index": "Cpu/Ppu", "Within": f"{result.cpu:.4f}", "Overall": f"{result.ppu:.4f}" if result.ppu else "N/A"})
    if result.cpl is not None:
        rows.append({"Index": "Cpl/Ppl", "Within": f"{result.cpl:.4f}", "Overall": f"{result.ppl:.4f}" if result.ppl else "N/A"})
    if result.cpm is not None:
        rows.append({"Index": "Cpm", "Within": f"{result.cpm:.4f}", "Overall": ""})
    if result.ppm_within is not None:
        rows.append({"Index": "PPM (expected)", "Within": f"{result.ppm_within:.1f}", "Overall": f"{result.ppm_overall:.1f}" if result.ppm_overall else "N/A"})

    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=["Index", "Within", "Overall"])
