"""
Chart generation for SPC Tool.
Generates control charts using matplotlib.
"""

import numpy as np
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.patches import Patch
from typing import Optional, List, Dict, Set
import io

from .xbar_r import XbarRResult, ControlLimits
from .control_rules import get_all_violation_indices


# ─── Style Constants ───────────────────────────────────────────────────────────
COLOR_DATA = "#2C3E50"        # Dark blue-grey for data points
COLOR_CL = "#27AE60"         # Green for center line
COLOR_UCL = "#E74C3C"        # Red for control limits
COLOR_LCL = "#E74C3C"        # Red for control limits
COLOR_ZONE_A = "#FADBD8"     # Light red (±3σ zone)
COLOR_ZONE_B = "#FEF9E7"     # Light yellow (±2σ zone)
COLOR_ZONE_C = "#EAFAF1"     # Light green (±1σ zone)
COLOR_VIOLATION = "#E74C3C"  # Red for violation markers
COLOR_USL = "#8E44AD"        # Purple for spec limits
COLOR_LSL = "#8E44AD"        # Purple for spec limits
FONT_FAMILY = "Microsoft YaHei"


def setup_chinese_font():
    """Configure matplotlib for Chinese characters."""
    plt.rcParams["font.sans-serif"] = [FONT_FAMILY, "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.dpi"] = 150


def generate_xbar_r_chart(result: XbarRResult,
                          title: str = "Xbar-R Control Chart",
                          show_zones: bool = True,
                          show_violations: bool = True,
                          figsize: tuple = (10, 6),
                          lang: str = "zh") -> Figure:
    """
    Generate Xbar-R control chart (dual panel: Xbar on top, R on bottom).

    Parameters
    ----------
    result : XbarRResult
        Analysis results from calculate_xbar_r()
    title : str
        Chart title
    show_zones : bool
        Show ±1σ, ±2σ zone shading
    show_violations : bool
        Highlight out-of-control points
    figsize : tuple
        Figure size (width, height)
    lang : str
        Language for labels ('zh' or 'en')

    Returns
    -------
    matplotlib.figure.Figure
    """
    setup_chinese_font()

    fig, (ax_xbar, ax_r) = plt.subplots(2, 1, figsize=figsize, sharex=True,
                                         gridspec_kw={"hspace": 0.35})

    x = np.arange(1, len(result.xbar) + 1)

    # ─── Xbar Chart ────────────────────────────────────────────────────────
    _draw_control_chart(
        ax=ax_xbar,
        x=x,
        data=result.xbar,
        limits=result.xbar_limits,
        violations=result.xbar_violations if show_violations else {},
        title="Xbar Chart" if lang == "en" else "Xbar 均值图",
        ylabel="Xbar",
        show_zones=show_zones,
    )

    # ─── R Chart ───────────────────────────────────────────────────────────
    _draw_control_chart(
        ax=ax_r,
        x=x,
        data=result.r,
        limits=result.r_limits,
        violations=result.r_violations if show_violations else {},
        title="R Chart" if lang == "en" else "R 极差图",
        ylabel="R",
        show_zones=show_zones,
    )

    xlabel = "Subgroup" if lang == "en" else "子组号"
    ax_r.set_xlabel(xlabel, fontsize=10)

    fig.suptitle(title, fontsize=13, fontweight="bold", y=0.98)
    fig.subplots_adjust(left=0.08, right=0.82, top=0.93, bottom=0.08, hspace=0.35)

    return fig


def _draw_control_chart(ax, x: np.ndarray, data: np.ndarray,
                        limits: ControlLimits,
                        violations: Dict[int, List[int]],
                        title: str, ylabel: str,
                        show_zones: bool = True):
    """Draw a single control chart panel."""

    ucl, cl, lcl = limits.ucl, limits.cl, limits.lcl
    sigma = (ucl - cl) / 3.0

    # Zone shading
    if show_zones and sigma > 0:
        ax.axhspan(cl - sigma, cl + sigma, color=COLOR_ZONE_C, alpha=0.3)
        ax.axhspan(cl + sigma, cl + 2 * sigma, color=COLOR_ZONE_B, alpha=0.3)
        ax.axhspan(cl - 2 * sigma, cl - sigma, color=COLOR_ZONE_B, alpha=0.3)
        ax.axhspan(cl + 2 * sigma, ucl, color=COLOR_ZONE_A, alpha=0.3)
        ax.axhspan(lcl, cl - 2 * sigma, color=COLOR_ZONE_A, alpha=0.3)

    # Control limits
    ax.axhline(ucl, color=COLOR_UCL, linestyle="--", linewidth=1.2)
    ax.axhline(cl, color=COLOR_CL, linestyle="-", linewidth=1.5)
    ax.axhline(lcl, color=COLOR_LCL, linestyle="--", linewidth=1.2)

    # Annotate limit values on the right margin
    ax.text(x[-1] + 0.5, ucl, f"UCL={ucl:.4f}", fontsize=8, va='center', color=COLOR_UCL)
    ax.text(x[-1] + 0.5, cl, f"CL={cl:.4f}", fontsize=8, va='center', color=COLOR_CL)
    if lcl > 0 or (ucl - lcl) > 0.001:
        ax.text(x[-1] + 0.5, lcl, f"LCL={lcl:.4f}", fontsize=8, va='center', color=COLOR_LCL)

    # Data line
    ax.plot(x, data, color=COLOR_DATA, marker="o", markersize=4,
            linewidth=1.0, zorder=3)

    # Violation markers
    if violations:
        all_violations = get_all_violation_indices(violations)
        viol_x = [x[i] for i in all_violations if i < len(x)]
        viol_y = [data[i] for i in all_violations if i < len(data)]
        ax.scatter(viol_x, viol_y, color=COLOR_VIOLATION, s=60, zorder=5,
                   marker="o", edgecolors="darkred", linewidths=1.5)
        # Add violation test number annotations
        for test_num, indices in violations.items():
            for idx in indices[:3]:  # Only annotate first few to avoid clutter
                if idx < len(x):
                    ax.annotate(str(test_num), (x[idx], data[idx]),
                                textcoords="offset points", xytext=(0, 8),
                                fontsize=7, color="red", ha='center', fontweight='bold')

    ax.set_title(title, fontsize=10, fontweight="bold")
    ax.set_ylabel(ylabel, fontsize=9)
    ax.grid(True, alpha=0.3, linestyle=":")


def generate_xbar_s_chart(result, title: str = "Xbar-S Control Chart",
                          show_zones: bool = True, show_violations: bool = True,
                          figsize: tuple = (10, 6), lang: str = "zh") -> Figure:
    """Generate Xbar-S control chart (dual panel: Xbar on top, S on bottom)."""
    setup_chinese_font()
    fig, (ax_xbar, ax_s) = plt.subplots(2, 1, figsize=figsize, sharex=True,
                                         gridspec_kw={"hspace": 0.3})
    x = np.arange(1, len(result.xbar) + 1)

    _draw_control_chart(
        ax=ax_xbar, x=x, data=result.xbar, limits=result.xbar_limits,
        violations=result.xbar_violations if show_violations else {},
        title="X̄ Chart" if lang == "en" else "X̄ 图", ylabel="X̄",
        show_zones=show_zones,
    )
    _draw_control_chart(
        ax=ax_s, x=x, data=result.s, limits=result.s_limits,
        violations=result.s_violations if show_violations else {},
        title="S Chart" if lang == "en" else "S 图", ylabel="S",
        show_zones=show_zones,
    )

    xlabel = "子组" if lang == "zh" else "Subgroup"
    ax_s.set_xlabel(xlabel, fontsize=11)
    fig.suptitle(title, fontsize=14, fontweight="bold", y=0.98)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    return fig


def generate_imr_chart(result, title: str = "I-MR Control Chart",
                       show_zones: bool = True, show_violations: bool = True,
                       figsize: tuple = (10, 6), lang: str = "zh") -> Figure:
    """Generate I-MR control chart (dual panel: I on top, MR on bottom)."""
    setup_chinese_font()
    fig, (ax_i, ax_mr) = plt.subplots(2, 1, figsize=figsize, sharex=False,
                                       gridspec_kw={"hspace": 0.3})

    x_i = np.arange(1, len(result.individuals) + 1)
    x_mr = np.arange(2, len(result.mr) + 2)  # MR starts from observation 2

    _draw_control_chart(
        ax=ax_i, x=x_i, data=result.individuals, limits=result.i_limits,
        violations=result.i_violations if show_violations else {},
        title="I Chart" if lang == "en" else "I 图 (个别值)",
        ylabel="X", show_zones=show_zones,
    )
    _draw_control_chart(
        ax=ax_mr, x=x_mr, data=result.mr, limits=result.mr_limits,
        violations=result.mr_violations if show_violations else {},
        title="MR Chart" if lang == "en" else "MR 图 (移动极差)",
        ylabel="MR", show_zones=show_zones,
    )

    xlabel = "观测" if lang == "zh" else "Observation"
    ax_mr.set_xlabel(xlabel, fontsize=11)
    fig.suptitle(title, fontsize=14, fontweight="bold", y=0.98)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    return fig


def generate_attribute_chart(result, title: str = None,
                             show_violations: bool = True,
                             figsize: tuple = (10, 4.5), lang: str = "zh") -> Figure:
    """Generate P/NP/C/U attribute control chart (single panel)."""
    setup_chinese_font()
    fig, ax = plt.subplots(1, 1, figsize=figsize)

    x = np.arange(1, result.num_subgroups + 1)

    chart_labels = {
        "P": ("P 图 (不合格品率)" if lang == "zh" else "P Chart (Proportion Nonconforming)", "p"),
        "NP": ("NP 图 (不合格品数)" if lang == "zh" else "NP Chart (Number Nonconforming)", "np"),
        "C": ("C 图 (缺陷数)" if lang == "zh" else "C Chart (Number of Defects)", "c"),
        "U": ("U 图 (单位缺陷数)" if lang == "zh" else "U Chart (Defects per Unit)", "u"),
    }

    chart_title, ylabel = chart_labels.get(result.chart_type, (result.chart_type, "Value"))
    if title:
        chart_title = title

    # Plot data
    ax.plot(x, result.statistic, color=COLOR_DATA, marker="o", markersize=5,
            linewidth=1.0, zorder=3)

    # Center line
    ax.axhline(result.cl, color=COLOR_CL, linestyle="-", linewidth=1.5,
               label=f"CL={result.cl:.4f}")

    # Control limits (may be variable)
    if result.constant_sample_size:
        ax.axhline(result.ucl[0], color=COLOR_UCL, linestyle="--", linewidth=1.2,
                   label=f"UCL={result.ucl[0]:.4f}")
        ax.axhline(result.lcl[0], color=COLOR_LCL, linestyle="--", linewidth=1.2,
                   label=f"LCL={result.lcl[0]:.4f}")
    else:
        ax.plot(x, result.ucl, color=COLOR_UCL, linestyle="--", linewidth=1.2,
                label="UCL (variable)")
        ax.plot(x, result.lcl, color=COLOR_LCL, linestyle="--", linewidth=1.2,
                label="LCL (variable)")

    # Violations
    if show_violations and result.violations:
        all_v = get_all_violation_indices(result.violations)
        viol_x = [x[i] for i in all_v if i < len(x)]
        viol_y = [result.statistic[i] for i in all_v if i < len(result.statistic)]
        ax.scatter(viol_x, viol_y, color=COLOR_VIOLATION, s=80, zorder=5,
                   marker="o", edgecolors="darkred", linewidths=1.5,
                   label=f"OOC ({len(all_v)} pts)")

    xlabel = "子组" if lang == "zh" else "Subgroup"
    ax.set_xlabel(xlabel, fontsize=11)
    ax.set_ylabel(ylabel, fontsize=10)
    ax.set_title(chart_title, fontsize=13, fontweight="bold")
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(True, alpha=0.3, linestyle=":")

    fig.tight_layout()
    return fig


def figure_to_bytes(fig: Figure, dpi: int = 200, format: str = "png") -> bytes:
    """Convert matplotlib figure to bytes."""
    buf = io.BytesIO()
    fig.savefig(buf, format=format, dpi=dpi, bbox_inches="tight")
    buf.seek(0)
    data = buf.read()
    plt.close(fig)
    return data


def save_figure(fig: Figure, path: str, dpi: int = 150):
    """Save figure to file."""
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
