"""
Process Capability Page.
"""

import dash
from dash import html, dcc, callback, Input, Output, State, no_update, dash_table
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import plotly.figure_factory as ff
import pandas as pd
import numpy as np
from scipy import stats
import base64, io

from core.capability import calculate_capability, test_normality

dash.register_page(__name__, path="/capability", name="过程能力", title="Process Capability")

layout = dbc.Container([
    html.H3("过程能力分析 (Process Capability)", className="mb-3"),
    dbc.Row([
        dbc.Col([
            dbc.Card([dbc.CardHeader("📂 数据导入"), dbc.CardBody([
                dcc.Upload(id="cap-upload", children=dbc.Button("上传 CSV/Excel", color="primary", className="w-100"), multiple=False),
                html.Div(id="cap-file-info", className="mt-2 text-muted small"),
            ])], className="mb-3"),
            dbc.Card([dbc.CardHeader("列选择"), dbc.CardBody([
                html.Label("数据列:"), dcc.Dropdown(id="cap-data-col", placeholder="选择数值列..."),
            ])], className="mb-3"),
            dbc.Card([dbc.CardHeader("规格限 (必填)"), dbc.CardBody([
                dbc.Row([
                    dbc.Col([html.Label("USL:"), dbc.Input(id="cap-usl", type="number", placeholder="必填")], width=6),
                    dbc.Col([html.Label("LSL:"), dbc.Input(id="cap-lsl", type="number", placeholder="必填")], width=6),
                ]),
                dbc.Row([
                    dbc.Col([html.Label("Target:"), dbc.Input(id="cap-target", type="number", placeholder="可选")], width=6),
                    dbc.Col([html.Label("子组大小:"), dbc.Input(id="cap-subgroup", type="number", value=1, min=1)], width=6),
                ], className="mt-2"),
            ])], className="mb-3"),
            dbc.Card([dbc.CardHeader("数据变换"), dbc.CardBody([
                dbc.RadioItems(id="cap-transform", options=[
                    {"label": " 无变换", "value": "none"},
                    {"label": " Box-Cox", "value": "boxcox"},
                    {"label": " Johnson", "value": "johnson"},
                ], value="none"),
            ])], className="mb-3"),
            dbc.Button("▶ 分析", id="cap-analyze", color="primary", size="lg", className="w-100"),
        ], width=3),
        dbc.Col([
            dcc.Loading(dcc.Graph(id="cap-chart", style={"height": "450px"}), type="circle"),
            html.Div(id="cap-results", className="mt-3"),
            dbc.Card([dbc.CardHeader("📋 解读"), dbc.CardBody(html.Pre(id="cap-interpretation", style={"whiteSpace": "pre-wrap", "fontSize": "13px"}))], className="mt-3"),
        ], width=9),
    ]),
    dcc.Store(id="cap-data-store"),
], fluid=True)


@callback(Output("cap-data-store","data"), Output("cap-file-info","children"), Output("cap-data-col","options"),
          Input("cap-upload","contents"), State("cap-upload","filename"), prevent_initial_call=True)
def on_upload(contents, filename):
    if not contents: return no_update, no_update, no_update
    decoded = base64.b64decode(contents.split(",")[1])
    try:
        df = pd.read_csv(io.BytesIO(decoded)) if filename.lower().endswith(".csv") else pd.read_excel(io.BytesIO(decoded), engine="xlrd" if filename.lower().endswith(".xls") else "openpyxl")
        numeric = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        return df.to_json(orient="split"), f"✓ {filename} ({len(df)} rows)", [{"label":c,"value":c} for c in numeric]
    except Exception as e:
        return no_update, f"❌ {e}", no_update


@callback(Output("cap-chart","figure"), Output("cap-results","children"), Output("cap-interpretation","children"),
          Input("cap-analyze","n_clicks"), State("cap-data-store","data"), State("cap-data-col","value"),
          State("cap-usl","value"), State("cap-lsl","value"), State("cap-target","value"),
          State("cap-subgroup","value"), State("cap-transform","value"), prevent_initial_call=True)
def on_analyze(n, data_json, col, usl, lsl, target, sg_size, transform):
    if not data_json or not col: return go.Figure(), "请选择数据列", ""
    if not usl and not lsl: return go.Figure(), "⚠️ 至少需要一个规格限", ""
    df = pd.read_json(io.StringIO(data_json), orient="split")
    try:
        data = df[col].dropna().values.astype(float)
        r = calculate_capability(data, usl=usl or None, lsl=lsl or None, target=target or None,
                                 subgroup_size=int(sg_size) if sg_size and int(sg_size) > 1 else None,
                                 transform=transform or "none")

        # Histogram + normal fit
        fig = go.Figure()
        fig.add_trace(go.Histogram(x=data, nbinsx=int(np.sqrt(len(data))), name="Data", opacity=0.6,
                                    marker_color="#3498DB", histnorm="probability density"))

        # Normal fit curves
        x_range = np.linspace(data.min() - 2*r.std_overall, data.max() + 2*r.std_overall, 200)
        fig.add_trace(go.Scatter(x=x_range, y=stats.norm.pdf(x_range, r.mean, r.std_overall),
                                  mode="lines", name=f"Overall (σ={r.std_overall:.4f})", line=dict(color="blue", width=2)))
        fig.add_trace(go.Scatter(x=x_range, y=stats.norm.pdf(x_range, r.mean, r.std_within),
                                  mode="lines", name=f"Within (σ={r.std_within:.4f})", line=dict(color="red", dash="dash", width=2)))

        # Spec limits
        if usl: fig.add_vline(x=usl, line_color="purple", line_width=2, annotation_text=f"USL={usl}")
        if lsl: fig.add_vline(x=lsl, line_color="purple", line_width=2, annotation_text=f"LSL={lsl}")
        if target: fig.add_vline(x=target, line_color="green", line_dash="dot", annotation_text=f"Target={target}")

        fig.update_layout(title="过程能力直方图", height=450, template="plotly_white",
                          legend=dict(orientation="h", y=-0.2), xaxis_title="Value", yaxis_title="Density")

        # Results table
        rows = []
        if r.cp is not None: rows.append({"指标": "Cp", "Within": f"{r.cp:.4f}", "Overall": f"{r.pp:.4f}" if r.pp else "-"})
        if r.cpk is not None: rows.append({"指标": "Cpk", "Within": f"{r.cpk:.4f}", "Overall": f"{r.ppk:.4f}" if r.ppk else "-"})
        if r.cpm is not None: rows.append({"指标": "Cpm", "Within": f"{r.cpm:.4f}", "Overall": "-"})
        if r.ppm_within is not None: rows.append({"指标": "PPM", "Within": f"{r.ppm_within:.0f}", "Overall": f"{r.ppm_overall:.0f}" if r.ppm_overall else "-"})

        table = dash_table.DataTable(data=rows, columns=[{"name":c,"id":c} for c in ["指标","Within","Overall"]],
                                     style_cell={"textAlign":"center","fontSize":"13px"},
                                     style_header={"fontWeight":"bold","backgroundColor":"#3498DB","color":"white"},
                                     style_data_conditional=[{"if":{"filter_query":'{指标} = "Cpk"'},"fontWeight":"bold"}])

        # Interpretation
        lines = []
        lines.append(f"n={r.n}, Mean={r.mean:.4f}")
        lines.append(f"σ_within={r.std_within:.6f}, σ_overall={r.std_overall:.6f}")
        lines.append(f"正态性: {'✅ 通过' if r.normality.is_normal else '❌ 非正态'} (AD p={'通过' if r.normality.ad_is_normal else '未通过'}, SW p={r.normality.sw_p_value:.4f})")
        if r.transformation and r.transformation != "None":
            lines.append(f"变换: {r.transformation}" + (f", λ={r.lambda_boxcox:.4f}" if r.lambda_boxcox else ""))
        if r.cpk is not None:
            lines.append(f"\nCpk = {r.cpk:.3f}")
            if r.cpk >= 1.67: lines.append("  → 🟢 优秀 (Cpk ≥ 1.67)")
            elif r.cpk >= 1.33: lines.append("  → 🟢 良好 (Cpk ≥ 1.33)")
            elif r.cpk >= 1.0: lines.append("  → 🟡 勉强 (1.0 ≤ Cpk < 1.33)")
            else: lines.append("  → 🔴 不足 (Cpk < 1.0)，必须改进")
        return fig, table, "\n".join(lines)
    except Exception as e:
        return go.Figure(), f"❌ {e}", ""
