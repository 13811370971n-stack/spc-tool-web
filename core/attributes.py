"""
Attribute Control Charts: P, NP, C, U.
Based on AIAG SPC Reference Manual.

P chart: proportion nonconforming (variable sample size)
NP chart: number nonconforming (constant sample size)
C chart: number of defects (constant sample size)
U chart: defects per unit (variable sample size)
"""

import numpy as np
import pandas as pd
from typing import Optional, List, Dict
from dataclasses import dataclass, field

from .control_rules import run_tests, get_all_violation_indices
from .xbar_r import ControlLimits


@dataclass
class AttributeChartResult:
    """Complete attribute control chart result."""
    # Chart type
    chart_type: str            # "P", "NP", "C", "U"

    # Statistics
    statistic: np.ndarray      # Plotted statistic (p, np, c, or u)
    sample_sizes: np.ndarray   # n_i for each subgroup
    counts: np.ndarray         # defective/defect counts

    # Control limits (may be variable for P and U charts)
    ucl: np.ndarray            # UCL per subgroup (variable if sample size varies)
    cl: float                  # Center line (constant)
    lcl: np.ndarray            # LCL per subgroup

    # Out-of-control test results
    violations: Dict[int, List[int]] = field(default_factory=dict)

    # Metadata
    num_subgroups: int = 0
    constant_sample_size: bool = True
    excluded_subgroups: List[int] = field(default_factory=list)

    # Phase
    phase: str = "I"

    @property
    def in_control(self) -> bool:
        return len(self.violations) == 0

    @property
    def avg_sample_size(self) -> float:
        return np.mean(self.sample_sizes)


def calculate_p_chart(defectives: np.ndarray,
                      sample_sizes: np.ndarray,
                      enabled_tests: Optional[List[int]] = None,
                      phase: str = "I",
                      exclude_subgroups: Optional[List[int]] = None) -> AttributeChartResult:
    """
    Calculate P chart (proportion nonconforming).

    Parameters
    ----------
    defectives : array-like
        Number of defective items per subgroup.
    sample_sizes : array-like
        Sample size per subgroup (can vary).
    enabled_tests : list of int, optional
        Default: [1, 2, 3, 4].
    phase : str
        "I" or "II".
    exclude_subgroups : list of int, optional
        Indices to exclude from limit calculation.

    Returns
    -------
    AttributeChartResult
    """
    if enabled_tests is None:
        enabled_tests = [1, 2, 3, 4]

    defectives = np.asarray(defectives, dtype=float)
    sample_sizes = np.asarray(sample_sizes, dtype=float)
    k = len(defectives)

    # Mask
    if exclude_subgroups:
        mask = np.ones(k, dtype=bool)
        mask[exclude_subgroups] = False
    else:
        mask = np.ones(k, dtype=bool)

    # P-bar (average proportion nonconforming)
    p_bar = np.sum(defectives[mask]) / np.sum(sample_sizes[mask])

    # Individual proportions
    p = defectives / sample_sizes

    # Control limits (variable if sample size varies)
    ucl = p_bar + 3 * np.sqrt(p_bar * (1 - p_bar) / sample_sizes)
    lcl = p_bar - 3 * np.sqrt(p_bar * (1 - p_bar) / sample_sizes)
    lcl = np.maximum(lcl, 0.0)  # LCL cannot be negative

    # For OOC tests, use average limits (since tests expect constant limits)
    avg_n = np.mean(sample_sizes[mask])
    ucl_avg = p_bar + 3 * np.sqrt(p_bar * (1 - p_bar) / avg_n)
    lcl_avg = max(p_bar - 3 * np.sqrt(p_bar * (1 - p_bar) / avg_n), 0.0)

    # Run OOC tests
    # For variable sample size charts:
    # - Test 1 (beyond 3σ): use INDIVIDUAL limits per point (not average)
    # - Tests 2-8 (pattern tests): use average limits (patterns need constant reference)
    violations = {}

    # Test 1: check each point against its own limits
    if 1 in enabled_tests:
        test1_violations = []
        for i in range(k):
            if p[i] > ucl[i] or p[i] < lcl[i]:
                test1_violations.append(i)
        if test1_violations:
            violations[1] = test1_violations

    # Tests 2-8: use average limits for pattern detection
    pattern_tests = [t for t in enabled_tests if t != 1]
    if pattern_tests:
        from .control_rules import run_tests as _run_tests
        pattern_violations = _run_tests(p, p_bar, ucl_avg, lcl_avg, pattern_tests)
        violations.update(pattern_violations)

    constant_n = np.all(sample_sizes == sample_sizes[0])

    return AttributeChartResult(
        chart_type="P",
        statistic=p,
        sample_sizes=sample_sizes,
        counts=defectives,
        ucl=ucl,
        cl=p_bar,
        lcl=lcl,
        violations=violations,
        num_subgroups=k,
        constant_sample_size=constant_n,
        excluded_subgroups=exclude_subgroups or [],
        phase=phase,
    )


def calculate_np_chart(defectives: np.ndarray,
                       sample_size: int,
                       enabled_tests: Optional[List[int]] = None,
                       phase: str = "I",
                       exclude_subgroups: Optional[List[int]] = None) -> AttributeChartResult:
    """
    Calculate NP chart (number of nonconforming items, constant sample size).

    Parameters
    ----------
    defectives : array-like
        Number of defective items per subgroup.
    sample_size : int
        Constant sample size for all subgroups.
    enabled_tests, phase, exclude_subgroups: see calculate_p_chart.

    Returns
    -------
    AttributeChartResult
    """
    if enabled_tests is None:
        enabled_tests = [1, 2, 3, 4]

    defectives = np.asarray(defectives, dtype=float)
    k = len(defectives)
    n = float(sample_size)
    sample_sizes = np.full(k, n)

    # Mask
    if exclude_subgroups:
        mask = np.ones(k, dtype=bool)
        mask[exclude_subgroups] = False
    else:
        mask = np.ones(k, dtype=bool)

    # np-bar
    p_bar = np.sum(defectives[mask]) / (np.sum(mask) * n)
    np_bar = n * p_bar

    # Control limits
    ucl_val = np_bar + 3 * np.sqrt(np_bar * (1 - p_bar))
    lcl_val = max(np_bar - 3 * np.sqrt(np_bar * (1 - p_bar)), 0.0)

    ucl = np.full(k, ucl_val)
    lcl = np.full(k, lcl_val)

    # OOC tests
    violations = run_tests(defectives, np_bar, ucl_val, lcl_val, enabled_tests)

    return AttributeChartResult(
        chart_type="NP",
        statistic=defectives,
        sample_sizes=sample_sizes,
        counts=defectives,
        ucl=ucl,
        cl=np_bar,
        lcl=lcl,
        violations=violations,
        num_subgroups=k,
        constant_sample_size=True,
        excluded_subgroups=exclude_subgroups or [],
        phase=phase,
    )


def calculate_c_chart(defects: np.ndarray,
                      enabled_tests: Optional[List[int]] = None,
                      phase: str = "I",
                      exclude_subgroups: Optional[List[int]] = None) -> AttributeChartResult:
    """
    Calculate C chart (number of defects, constant opportunity/area).

    Parameters
    ----------
    defects : array-like
        Number of defects per inspection unit.
    enabled_tests, phase, exclude_subgroups: see calculate_p_chart.

    Returns
    -------
    AttributeChartResult
    """
    if enabled_tests is None:
        enabled_tests = [1, 2, 3, 4]

    defects = np.asarray(defects, dtype=float)
    k = len(defects)
    sample_sizes = np.ones(k)  # C chart assumes constant inspection unit

    # Mask
    if exclude_subgroups:
        mask = np.ones(k, dtype=bool)
        mask[exclude_subgroups] = False
    else:
        mask = np.ones(k, dtype=bool)

    # c-bar
    c_bar = np.mean(defects[mask])

    # Control limits
    ucl_val = c_bar + 3 * np.sqrt(c_bar)
    lcl_val = max(c_bar - 3 * np.sqrt(c_bar), 0.0)

    ucl = np.full(k, ucl_val)
    lcl = np.full(k, lcl_val)

    # OOC tests
    violations = run_tests(defects, c_bar, ucl_val, lcl_val, enabled_tests)

    return AttributeChartResult(
        chart_type="C",
        statistic=defects,
        sample_sizes=sample_sizes,
        counts=defects,
        ucl=ucl,
        cl=c_bar,
        lcl=lcl,
        violations=violations,
        num_subgroups=k,
        constant_sample_size=True,
        excluded_subgroups=exclude_subgroups or [],
        phase=phase,
    )


def calculate_u_chart(defects: np.ndarray,
                      sample_sizes: np.ndarray,
                      enabled_tests: Optional[List[int]] = None,
                      phase: str = "I",
                      exclude_subgroups: Optional[List[int]] = None) -> AttributeChartResult:
    """
    Calculate U chart (defects per unit, variable sample size).

    Parameters
    ----------
    defects : array-like
        Number of defects per subgroup.
    sample_sizes : array-like
        Number of inspection units per subgroup.
    enabled_tests, phase, exclude_subgroups: see calculate_p_chart.

    Returns
    -------
    AttributeChartResult
    """
    if enabled_tests is None:
        enabled_tests = [1, 2, 3, 4]

    defects = np.asarray(defects, dtype=float)
    sample_sizes = np.asarray(sample_sizes, dtype=float)
    k = len(defects)

    # Mask
    if exclude_subgroups:
        mask = np.ones(k, dtype=bool)
        mask[exclude_subgroups] = False
    else:
        mask = np.ones(k, dtype=bool)

    # u-bar
    u_bar = np.sum(defects[mask]) / np.sum(sample_sizes[mask])

    # Individual u values
    u = defects / sample_sizes

    # Variable control limits
    ucl = u_bar + 3 * np.sqrt(u_bar / sample_sizes)
    lcl = u_bar - 3 * np.sqrt(u_bar / sample_sizes)
    lcl = np.maximum(lcl, 0.0)

    # OOC tests
    # Test 1: use individual limits per point
    # Tests 2-8: use average limits for pattern detection
    avg_n = np.mean(sample_sizes[mask])
    ucl_avg = u_bar + 3 * np.sqrt(u_bar / avg_n)
    lcl_avg = max(u_bar - 3 * np.sqrt(u_bar / avg_n), 0.0)

    violations = {}

    # Test 1: individual limits
    if 1 in enabled_tests:
        test1_violations = []
        for i in range(k):
            if u[i] > ucl[i] or u[i] < lcl[i]:
                test1_violations.append(i)
        if test1_violations:
            violations[1] = test1_violations

    # Tests 2-8: pattern tests with average limits
    pattern_tests = [t for t in enabled_tests if t != 1]
    if pattern_tests:
        pattern_violations = run_tests(u, u_bar, ucl_avg, lcl_avg, pattern_tests)
        violations.update(pattern_violations)

    constant_n = np.all(sample_sizes == sample_sizes[0])

    return AttributeChartResult(
        chart_type="U",
        statistic=u,
        sample_sizes=sample_sizes,
        counts=defects,
        ucl=ucl,
        cl=u_bar,
        lcl=lcl,
        violations=violations,
        num_subgroups=k,
        constant_sample_size=constant_n,
        excluded_subgroups=exclude_subgroups or [],
        phase=phase,
    )


def summary_table(result: AttributeChartResult) -> pd.DataFrame:
    """Generate summary statistics table."""
    if result.constant_sample_size:
        ucl_str = f"{result.ucl[0]:.4f}"
        lcl_str = f"{result.lcl[0]:.4f}"
    else:
        ucl_str = f"{np.mean(result.ucl):.4f} (avg)"
        lcl_str = f"{np.mean(result.lcl):.4f} (avg)"

    chart_label = {
        "P": "P (Proportion)",
        "NP": "NP (Count)",
        "C": "C (Defects)",
        "U": "U (Defects/Unit)",
    }.get(result.chart_type, result.chart_type)

    rows = [
        {
            "Chart": chart_label,
            "UCL": ucl_str,
            "CL": f"{result.cl:.4f}",
            "LCL": lcl_str,
            "In Control": "✓" if result.in_control else "✗",
            "Violations": str(list(result.violations.keys())) if result.violations else "None",
        },
    ]
    return pd.DataFrame(rows)
