"""
I-MR Control Chart Page.
"""

import dash
from dash import html, dcc, callback, Input, Output, State, no_update, dash_table
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
import base64
import io

from core.imr import calculate_imr
from core.control_rules import get_all_violation_indices

dash.register_page(__name__, path="/imr", name="I-MR", title="I-MR Control Chart")

layout = dbc.Container([
    html.H3("I-MR 控制图 (个别值-移动极差)", className="mb-3"),
    dbc.Row([
        dbc.Col([
            dbc.Card([dbc.CardHeader("📂 数据导入"), dbc.CardBody([
                dcc.Upload(id="imr-upload", children=dbc.Button("上传 CSV/Excel", color="primary", className="w-100"), multiple=False),
                html.Div(id="imr-file-info", className="mt-2 text-muted small"),
            ])], className="mb-3"),
            dbc.Card([dbc.CardHeader("列选择"), dbc.CardBody([
                html.Label("数据列:"), dcc.Dropdown(id="imr-data-col", placeholder="选择数值列..."),
            ])], className="mb-3"),
            dbc.Card([dbc.CardHeader("参数"), dbc.CardBody([
                dbc.Row([
                    dbc.Col([html.Label("USL:"), dbc.Input(id="imr-usl", type="number", placeholder="N/A")], width=6),
                    dbc.Col([html.Label("LSL:"), dbc.Input(id="imr-lsl", type="number", placeholder="N/A")], width=6),
                ]),
                html.Label("判异规则:", className="mt-2"),
                dbc.Checklist(id="imr-tests", options=[{"label": f" Test {i}", "value": i} for i in range(1, 9)], value=[1,2,3,4], inline=True, className="small"),
            ])], className="mb-3"),
            dbc.Button("▶ 分析", id="imr-analyze", color="primary", size="lg", className="w-100"),
        ], width=3),
        dbc.Col([
            dcc.Loading(dcc.Graph(id="imr-chart", style={"height": "500px"}), type="circle"),
            html.Div(id="imr-results", className="mt-3"),
            dbc.Card([dbc.CardHeader("📋 分析解读"), dbc.CardBody(html.Pre(id="imr-interpretation", style={"whiteSpace": "pre-wrap", "fontSize": "13px"}))], className="mt-3"),
        ], width=9),
    ]),
    dcc.Store(id="imr-data-store"),
], fluid=True)


@callback(Output("imr-data-store","data"), Output("imr-file-info","children"), Output("imr-data-col","options"),
          Input("imr-upload","contents"), State("imr-upload","filename"), prevent_initial_call=True)
def on_upload(contents, filename):
    if not contents: return no_update, no_update, no_update
    decoded = base64.b64decode(contents.split(",")[1])
    try:
        df = pd.read_csv(io.BytesIO(decoded)) if filename.lower().endswith(".csv") else pd.read_excel(io.BytesIO(decoded), engine="xlrd" if filename.lower().endswith(".xls") else "openpyxl")
        numeric = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        return df.to_json(orient="split"), f"✓ {filename} ({len(df)} rows)", [{"label":c,"value":c} for c in numeric]
    except Exception as e:
        return no_update, f"❌ {e}", no_update


@callback(Output("imr-chart","figure"), Output("imr-results","children"), Output("imr-interpretation","children"),
          Input("imr-analyze","n_clicks"), State("imr-data-store","data"), State("imr-data-col","value"),
          State("imr-usl","value"), State("imr-lsl","value"), State("imr-tests","value"), prevent_initial_call=True)
def on_analyze(n, data_json, col, usl, lsl, tests):
    if not data_json or not col: return go.Figure(), "请选择数据列", ""
    df = pd.read_json(io.StringIO(data_json), orient="split")
    try:
        data = df[col].dropna().values.astype(float)
        r = calculate_imr(data, enabled_tests=tests or [1,2,3,4], usl=usl or None, lsl=lsl or None)

        fig = make_subplots(rows=2, cols=1, subplot_titles=("I 个别值图","MR 移动极差图"), vertical_spacing=0.12)
        x_i = list(range(1, len(r.individuals)+1))
        x_mr = list(range(2, len(r.mr)+2))

        fig.add_trace(go.Scatter(x=x_i, y=r.individuals, mode="lines+markers", name="I", line=dict(color="#2C3E50"), marker=dict(size=4)), row=1, col=1)
        fig.add_hline(y=r.i_limits.ucl, line_dash="dash", line_color="red", annotation_text=f"UCL={r.i_limits.ucl:.4f}", row=1, col=1)
        fig.add_hline(y=r.i_limits.cl, line_color="green", line_width=2, annotation_text=f"CL={r.i_limits.cl:.4f}", row=1, col=1)
        fig.add_hline(y=r.i_limits.lcl, line_dash="dash", line_color="red", annotation_text=f"LCL={r.i_limits.lcl:.4f}", row=1, col=1)
        if r.i_violations:
            vi = get_all_violation_indices(r.i_violations)
            fig.add_trace(go.Scatter(x=[x_i[i] for i in vi], y=[r.individuals[i] for i in vi], mode="markers", name="失控(I)", marker=dict(color="red", size=10, symbol="circle-open", line=dict(width=2))), row=1, col=1)

        fig.add_trace(go.Scatter(x=x_mr, y=r.mr, mode="lines+markers", name="MR", line=dict(color="#2C3E50"), marker=dict(size=4)), row=2, col=1)
        fig.add_hline(y=r.mr_limits.ucl, line_dash="dash", line_color="red", annotation_text=f"UCL={r.mr_limits.ucl:.4f}", row=2, col=1)
        fig.add_hline(y=r.mr_limits.cl, line_color="green", line_width=2, annotation_text=f"CL={r.mr_limits.cl:.4f}", row=2, col=1)

        fig.update_layout(height=500, showlegend=True, legend=dict(orientation="h", y=-0.15), template="plotly_white")
        fig.update_xaxes(title_text="观测号", row=2, col=1)

        table = dash_table.DataTable(
            data=[{"图表":"I","UCL":f"{r.i_limits.ucl:.4f}","CL":f"{r.i_limits.cl:.4f}","LCL":f"{r.i_limits.lcl:.4f}","状态":"✅" if r.i_in_control else "❌"},
                  {"图表":"MR","UCL":f"{r.mr_limits.ucl:.4f}","CL":f"{r.mr_limits.cl:.4f}","LCL":"0","状态":"✅" if r.mr_in_control else "❌"}],
            columns=[{"name":c,"id":c} for c in ["图表","UCL","CL","LCL","状态"]],
            style_cell={"textAlign":"center","fontSize":"13px"}, style_header={"fontWeight":"bold","backgroundColor":"#3498DB","color":"white"})

        lines = ["✅ 过程受控" if r.in_control else "❌ 过程失控"]
        if r.i_violations:
            for t, idx in r.i_violations.items():
                lines.append(f"  判异{t}: 观测 {[i+1 for i in idx[:10]]}")
        lines.append(f"\nσ_within={r.sigma_within:.6f}, σ_overall={r.sigma_overall:.6f}")
        if r.capability and "Cpk" in r.capability: lines.append(f"Cpk={r.capability['Cpk']:.3f}")
        return fig, table, "\n".join(lines)
    except Exception as e:
        return go.Figure(), f"❌ {e}", ""
