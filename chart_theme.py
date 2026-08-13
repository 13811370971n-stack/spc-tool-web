"""
Plotly chart styling - McKinsey theme for SPC Tool Web.
Shared template for consistent chart appearance across all pages.
"""

import plotly.graph_objects as go
import plotly.io as pio

# McKinsey color palette
NAVY = "#051C2C"
BLUE = "#0C2E4E"
STEEL = "#1E3A5F"
TEAL = "#00A0AF"
GOLD = "#C5A572"
LIGHT = "#F5F7FA"
MUTED = "#8B9DAF"
RED = "#D63031"
GREEN = "#00B894"

# Chart colors
COLOR_DATA = NAVY          # Data line
COLOR_UCL = RED            # Upper control limit
COLOR_LCL = RED            # Lower control limit
COLOR_CL = GREEN           # Center line
COLOR_VIOLATION = RED      # Out-of-control markers
COLOR_ZONE_A = "#FADBD8"   # ±3σ zone
COLOR_ZONE_B = "#FEF9E7"   # ±2σ zone
COLOR_ZONE_C = "#EAFAF1"   # ±1σ zone


# Create a custom Plotly template
mckinsey_template = go.layout.Template(
    layout=go.Layout(
        font=dict(family="Inter, sans-serif", color=NAVY, size=12),
        title=dict(font=dict(size=16, color=NAVY, family="Inter, sans-serif"), x=0.5, xanchor="center"),
        paper_bgcolor="white",
        plot_bgcolor="white",
        xaxis=dict(
            gridcolor="#E2E8F0",
            gridwidth=0.5,
            linecolor="#E2E8F0",
            title_font=dict(size=12, color=MUTED),
            tickfont=dict(size=10, color=MUTED),
        ),
        yaxis=dict(
            gridcolor="#E2E8F0",
            gridwidth=0.5,
            linecolor="#E2E8F0",
            title_font=dict(size=12, color=MUTED),
            tickfont=dict(size=10, color=MUTED),
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.2,
            xanchor="center",
            x=0.5,
            font=dict(size=11),
        ),
        margin=dict(l=60, r=30, t=60, b=60),
    )
)

# Register template
pio.templates["mckinsey"] = mckinsey_template
pio.templates.default = "mckinsey"


def apply_mckinsey_style(fig: go.Figure) -> go.Figure:
    """Apply McKinsey styling to an existing figure."""
    fig.update_layout(template="mckinsey")
    return fig
