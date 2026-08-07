"""Placeholder pages for unimplemented chart types."""
import dash
from dash import html
import dash_bootstrap_components as dbc

# Register all placeholder pages
for path, name in [
    ("/xbar-s", "Xbar-S"), ("/imr", "I-MR"),
    ("/p-chart", "P Chart"), ("/np-chart", "NP Chart"),
    ("/c-chart", "C Chart"), ("/u-chart", "U Chart"),
    ("/ewma", "EWMA"), ("/zmr", "Z-MR"),
    ("/capability", "过程能力"), ("/normality", "正态性检验"),
    ("/ai-settings", "AI Settings"),
]:
    dash.register_page(
        f"placeholder_{name.replace(' ','_').lower()}",
        path=path, name=name,
        layout=dbc.Container([
            html.H3(f"🚧 {name}", className="mt-5 text-center"),
            html.P("Coming Soon / 即将实现", className="text-center text-muted"),
            html.P("请先使用 Xbar-R 页面体验完整功能。", className="text-center"),
            dbc.Button("← 返回 Xbar-R", href="/xbar-r", color="primary", className="d-block mx-auto mt-3"),
        ], fluid=True),
    )
