"""Home page."""
import dash
from dash import html
import dash_bootstrap_components as dbc

dash.register_page(__name__, path="/", name="Home", title="SPC Tool")

layout = dbc.Container([
    dbc.Row([
        dbc.Col([
            html.H1("📊 SPC Tool", className="text-center mt-5"),
            html.H4("统计过程控制工具 (Web Version)", className="text-center text-muted mb-5"),
            html.Hr(),
            dbc.Row([
                dbc.Col(dbc.Card([
                    dbc.CardBody([
                        html.H5("📈 计量型控制图"),
                        html.P("Xbar-R / Xbar-S / I-MR"),
                        dbc.Button("Xbar-R →", href="/xbar-r", color="primary", size="sm"),
                    ])
                ]), width=4),
                dbc.Col(dbc.Card([
                    dbc.CardBody([
                        html.H5("🔴 计数型控制图"),
                        html.P("P / NP / C / U"),
                        dbc.Button("P Chart →", href="/p-chart", color="primary", size="sm"),
                    ])
                ]), width=4),
                dbc.Col(dbc.Card([
                    dbc.CardBody([
                        html.H5("🎯 过程能力"),
                        html.P("Cp/Cpk/Pp/Ppk + Box-Cox"),
                        dbc.Button("能力分析 →", href="/capability", color="primary", size="sm"),
                    ])
                ]), width=4),
            ], className="mb-4"),
            dbc.Row([
                dbc.Col(dbc.Card([
                    dbc.CardBody([
                        html.H5("〰️ 特殊控制图"),
                        html.P("EWMA / Z-MR"),
                        dbc.Button("EWMA →", href="/ewma", color="secondary", size="sm"),
                    ])
                ]), width=4),
                dbc.Col(dbc.Card([
                    dbc.CardBody([
                        html.H5("🔔 正态性检验"),
                        html.P("AD / SW / KS 检验"),
                        dbc.Button("检验 →", href="/normality", color="secondary", size="sm"),
                    ])
                ]), width=4),
                dbc.Col(dbc.Card([
                    dbc.CardBody([
                        html.H5("🤖 AI 增强"),
                        html.P("LLM 深层分析"),
                        dbc.Button("设置 →", href="/ai-settings", color="secondary", size="sm"),
                    ])
                ]), width=4),
            ]),
            html.Hr(className="mt-5"),
            html.P("Based on AIAG SPC Reference Manual (2026 Edition)", className="text-center text-muted small"),
        ], width=10, className="mx-auto"),
    ]),
], fluid=True)
