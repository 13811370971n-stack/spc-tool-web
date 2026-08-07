"""
EWMA (Exponentially Weighted Moving Average) Control Chart Engine.
Based on AIAG SPC Reference Manual.

EWMA is sensitive to small sustained shifts in the process mean.
Z_i = λ * X_i + (1 - λ) * Z_{i-1}  where Z_0 = μ_0 (target or X-bar)

Control limits widen over time:
UCL_i = μ_0 + L * σ * sqrt(λ/(2-λ) * [1-(1-λ)^(2i)])
LCL_i = μ_0 - L * σ * sqrt(λ/(2-λ) * [1-(1-λ)^(2i)])

Steady-state limits (as i → ∞):
UCL = μ_0 + L * σ * sqrt(λ/(2-λ))
LCL = μ_0 - L * σ * sqrt(λ/(2-λ))
"""

import numpy as np
import pandas as pd
from typing import Optional, List, Dict
from dataclasses import dataclass, field

from .xbar_r import ControlLimits


@dataclass
class EWMAResult:
    """Complete EWMA analysis result."""
    # EWMA statistics
    ewma: np.ndarray             # Z_i values
    raw_data: np.ndarray         # Original X_i values

    # Parameters
    lambda_: float               # Smoothing constant (0 < λ ≤ 1)
    L: float                     # Control limit width (typically 3)
    target: float                # μ_0 (target or process mean)
    sigma: float                 # Process std deviation

    # Control limits (time-varying)
    ucl: np.ndarray              # UCL_i for each point
    cl: float                    # Center line = target
    lcl: np.ndarray              # LCL_i for each point

    # Steady-state limits
    ucl_ss: float                # Steady-state UCL
    lcl_ss: float                # Steady-state LCL

    # Violations (points beyond limits)
    violations: List[int] = field(default_factory=list)

    # Metadata
    num_observations: int = 0

    @property
    def in_control(self) -> bool:
        return len(self.violations) == 0


def calculate_ewma(data: np.ndarray,
                   lambda_: float = 0.2,
                   L: float = 3.0,
                   target: Optional[float] = None,
                   sigma: Optional[float] = None,
                   use_steady_state: bool = False) -> EWMAResult:
    """
    Calculate EWMA control chart.

    Parameters
    ----------
    data : np.ndarray
        1D array of individual measurements or subgroup means.
    lambda_ : float
        Smoothing constant (0 < λ ≤ 1). Default 0.2.
        - Small λ (0.05-0.1): sensitive to small shifts
        - Large λ (0.2-0.4): less smoothing, more responsive
    L : float
        Control limit multiplier. Default 3.0.
        Common: L=2.7 for λ=0.1, L=2.9 for λ=0.2, L=3.0 for λ=0.25
    target : float, optional
        Process target μ_0. Defaults to mean of data.
    sigma : float, optional
        Process std deviation. Defaults to MR-bar/d2 estimate.
    use_steady_state : bool
        If True, use constant steady-state limits instead of time-varying.

    Returns
    -------
    EWMAResult
    """
    data = np.asarray(data, dtype=float).flatten()
    data = data[~np.isnan(data)]
    n = len(data)

    if n < 3:
        raise ValueError("Need at least 3 observations for EWMA chart.")

    if lambda_ <= 0 or lambda_ > 1:
        raise ValueError("Lambda must be in (0, 1].")

    # Estimate target if not provided
    if target is None:
        target = np.mean(data)

    # Estimate sigma if not provided (using MR-bar/d2)
    if sigma is None:
        mr = np.abs(np.diff(data))
        mr_bar = np.mean(mr)
        d2 = 1.128  # d2 for n=2
        sigma = mr_bar / d2

    # Calculate EWMA
    ewma = np.zeros(n)
    ewma[0] = lambda_ * data[0] + (1 - lambda_) * target
    for i in range(1, n):
        ewma[i] = lambda_ * data[i] + (1 - lambda_) * ewma[i - 1]

    # Control limits
    if use_steady_state:
        # Constant steady-state limits
        ss_factor = L * sigma * np.sqrt(lambda_ / (2 - lambda_))
        ucl = np.full(n, target + ss_factor)
        lcl = np.full(n, target - ss_factor)
        ucl_ss = target + ss_factor
        lcl_ss = target - ss_factor
    else:
        # Time-varying limits
        ucl = np.zeros(n)
        lcl = np.zeros(n)
        for i in range(n):
            factor = L * sigma * np.sqrt(lambda_ / (2 - lambda_) * (1 - (1 - lambda_) ** (2 * (i + 1))))
            ucl[i] = target + factor
            lcl[i] = target - factor

        # Steady-state for reference
        ss_factor = L * sigma * np.sqrt(lambda_ / (2 - lambda_))
        ucl_ss = target + ss_factor
        lcl_ss = target - ss_factor

    # Detect violations
    violations = []
    for i in range(n):
        if ewma[i] > ucl[i] or ewma[i] < lcl[i]:
            violations.append(i)

    return EWMAResult(
        ewma=ewma,
        raw_data=data,
        lambda_=lambda_,
        L=L,
        target=target,
        sigma=sigma,
        ucl=ucl,
        cl=target,
        lcl=lcl,
        ucl_ss=ucl_ss,
        lcl_ss=lcl_ss,
        violations=violations,
        num_observations=n,
    )


def summary_table(result: EWMAResult) -> pd.DataFrame:
    """Generate summary table."""
    rows = [
        {
            "Chart": "EWMA",
            "λ": f"{result.lambda_:.3f}",
            "L": f"{result.L:.1f}",
            "Target (CL)": f"{result.target:.4f}",
            "UCL (ss)": f"{result.ucl_ss:.4f}",
            "LCL (ss)": f"{result.lcl_ss:.4f}",
            "σ": f"{result.sigma:.4f}",
            "In Control": "✓" if result.in_control else "✗",
            "OOC Points": str(len(result.violations)),
        },
    ]
    return pd.DataFrame(rows)
