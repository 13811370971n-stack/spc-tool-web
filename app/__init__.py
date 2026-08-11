"""
SPC Tool Web Application Factory.
Creates and configures the Dash app with all pages.
"""

import dash
from dash import Dash, html, dcc
import dash_bootstrap_components as dbc


def create_app() -> Dash:
    """Create and configure the Dash application."""
    import os
    pages_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "pages")

    app = Dash(
        __name__,
        use_pages=True,
        pages_folder=pages_dir,
        assets_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets"),
        external_stylesheets=[
            dbc.themes.BOOTSTRAP,
            dbc.icons.BOOTSTRAP,
            "https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap",
        ],
        suppress_callback_exceptions=True,
        title="SPC Tool",
        meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
    )

    # Sidebar navigation
    sidebar = dbc.Nav(
        [
            dbc.NavLink(
                [html.I(className="bi bi-bar-chart-line me-2"), "Xbar-R"],
                href="/xbar-r", active="exact",
            ),
            dbc.NavLink(
                [html.I(className="bi bi-bar-chart me-2"), "Xbar-S"],
                href="/xbar-s", active="exact",
            ),
            dbc.NavLink(
                [html.I(className="bi bi-graph-up me-2"), "I-MR"],
                href="/imr", active="exact",
            ),
            html.Hr(className="my-2"),
            dbc.NavLink(
                [html.I(className="bi bi-pie-chart me-2"), "P Chart"],
                href="/p-chart", active="exact",
            ),
            dbc.NavLink(
                [html.I(className="bi bi-pie-chart-fill me-2"), "NP Chart"],
                href="/np-chart", active="exact",
            ),
            dbc.NavLink(
                [html.I(className="bi bi-grid me-2"), "C Chart"],
                href="/c-chart", active="exact",
            ),
            dbc.NavLink(
                [html.I(className="bi bi-grid-fill me-2"), "U Chart"],
                href="/u-chart", active="exact",
            ),
            html.Hr(className="my-2"),
            dbc.NavLink(
                [html.I(className="bi bi-activity me-2"), "EWMA"],
                href="/ewma", active="exact",
            ),
            dbc.NavLink(
                [html.I(className="bi bi-rulers me-2"), "Z-MR"],
                href="/zmr", active="exact",
            ),
            html.Hr(className="my-2"),
            dbc.NavLink(
                [html.I(className="bi bi-bullseye me-2"), "过程能力"],
                href="/capability", active="exact",
            ),
            dbc.NavLink(
                [html.I(className="bi bi-bell me-2"), "正态性检验"],
                href="/normality", active="exact",
            ),
        ],
        vertical=True,
        pills=True,
        className="p-3",
    )

    app.layout = dbc.Container([
        # Header
        dbc.Navbar(
            dbc.Container([
                dbc.NavbarBrand([
                    html.Span("SPC", style={"color": "#C5A572", "fontWeight": "800"}),
                    html.Span(" Tool", style={"fontWeight": "400"}),
                ], className="fs-4"),
                dbc.Nav([
                    dbc.NavItem(dbc.NavLink("AI Settings", href="/ai-settings", className="small")),
                ], navbar=True),
            ]),
            color="dark", dark=True, className="mb-0",
        ),
        # Body: sidebar + content
        dbc.Row([
            dbc.Col(sidebar, width=2, className="border-end",
                    style={"overflowY": "auto", "height": "calc(100vh - 56px)", "position": "fixed", "top": "56px"}),
            dbc.Col(
                html.Div(dash.page_container, className="p-4"),
                width=10, className="ms-auto",
                style={"marginLeft": "16.67%"},
            ),
        ], className="g-0"),
    ], fluid=True, className="p-0")

    return app
