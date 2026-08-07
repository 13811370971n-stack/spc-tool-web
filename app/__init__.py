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
        external_stylesheets=[dbc.themes.FLATLY, dbc.icons.BOOTSTRAP],
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
            dbc.NavLink(
                [html.I(className="bi bi-circle me-2"), "P Chart"],
                href="/p-chart", active="exact",
            ),
            dbc.NavLink(
                [html.I(className="bi bi-circle-fill me-2"), "NP Chart"],
                href="/np-chart", active="exact",
            ),
            dbc.NavLink(
                [html.I(className="bi bi-hexagon me-2"), "C Chart"],
                href="/c-chart", active="exact",
            ),
            dbc.NavLink(
                [html.I(className="bi bi-hexagon-fill me-2"), "U Chart"],
                href="/u-chart", active="exact",
            ),
            dbc.NavLink(
                [html.I(className="bi bi-activity me-2"), "EWMA"],
                href="/ewma", active="exact",
            ),
            dbc.NavLink(
                [html.I(className="bi bi-rulers me-2"), "Z-MR"],
                href="/zmr", active="exact",
            ),
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
        className="bg-light p-3",
    )

    app.layout = dbc.Container([
        # Header
        dbc.Navbar(
            dbc.Container([
                dbc.NavbarBrand("📊 SPC Tool", className="fs-4 fw-bold"),
                dbc.Nav([
                    dbc.NavItem(dbc.NavLink("🌐 EN/中", id="btn-lang", href="#")),
                    dbc.NavItem(dbc.NavLink("🤖 AI Settings", href="/ai-settings")),
                ], navbar=True),
            ]),
            color="dark", dark=True, className="mb-3",
        ),
        # Body: sidebar + content
        dbc.Row([
            dbc.Col(sidebar, width=2, className="border-end vh-100 position-fixed",
                    style={"overflowY": "auto", "top": "56px"}),
            dbc.Col(
                dash.page_container,
                width=10, className="ms-auto",
                style={"marginLeft": "16.67%"},
            ),
        ]),
    ], fluid=True)

    return app
