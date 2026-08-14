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
                html.Hr(className="my-2"),
                dbc.Button("📋 加载Demo数据", id="cap-demo-btn", color="outline-secondary", size="sm", className="w-100"),
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


@callback(Output("cap-data-store","data"), Output("cap-file-info","children"), Output("cap-data-col","options"), Output("cap-data-col","value"),
          Output("cap-usl","value"), Output("cap-lsl","value"), Output("cap-transform","value"),
          Input("cap-upload","contents"), Input("cap-demo-btn","n_clicks"), State("cap-upload","filename"), prevent_initial_call=True)
def on_upload(contents, demo, filename):
    from dash import ctx
    triggered = ctx.triggered_id
    sel_col = None; usl_val = lsl_val = None; transform_val = "none"

    if triggered == "cap-demo-btn":
        from demo_loader import load_demo_data
        dj, config = load_demo_data("capability")
        if not dj: return no_update,"❌",no_update,no_update,no_update,no_update,no_update
        df = pd.read_json(io.StringIO(dj), orient="split")
        filename = config["file"]; sel_col = config["data_col"]
        usl_val = config.get("usl"); lsl_val = config.get("lsl")
        transform_val = config.get("transform", "none")
    elif contents:
        decoded = base64.b64decode(contents.split(",")[1])
        try:
            df = pd.read_csv(io.BytesIO(decoded)) if filename.lower().endswith(".csv") else pd.read_excel(io.BytesIO(decoded), engine="xlrd" if filename.lower().endswith(".xls") else "openpyxl")
        except Exception as e:
            return no_update, f"❌ {e}", no_update, no_update, no_update, no_update, no_update
    else:
        return no_update, no_update, no_update, no_update, no_update, no_update, no_update

    numeric = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    info = f"✓ {filename} ({len(df)} rows)" + (" 📋 Demo" if triggered == "cap-demo-btn" else "")
    return (df.to_json(orient="split"), info, [{"label":c,"value":c} for c in numeric],
            sel_col or no_update, usl_val or no_update, lsl_val or no_update, transform_val)


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

        # ─── Minitab-style Capability Chart ───
        fig = go.Figure()

        # Histogram
        fig.add_trace(go.Histogram(x=data, nbinsx=int(np.sqrt(len(data))),
                                    opacity=0.65, marker_color="#6BAED6",
                                    histnorm="probability density", showlegend=False))

        # Normal fit curves
        x_range = np.linspace(data.min() - 3*r.std_overall, data.max() + 3*r.std_overall, 300)
        # Overall: solid dark red
        fig.add_trace(go.Scatter(x=x_range, y=stats.norm.pdf(x_range, r.mean, r.std_overall),
                                  mode="lines", name="Overall",
                                  line=dict(color="#8B0000", width=2.5)))
        # Within: dashed dark red
        fig.add_trace(go.Scatter(x=x_range, y=stats.norm.pdf(x_range, r.mean, r.std_within),
                                  mode="lines", name="Within",
                                  line=dict(color="#8B0000", dash="dash", width=2)))

        # Spec limits (vertical lines at top, Minitab style)
        if lsl:
            fig.add_vline(x=lsl, line_color="#000000", line_width=1.5, line_dash="dash")
            fig.add_annotation(x=lsl, y=1.05, yref="paper", text="LSL", showarrow=False,
                             font=dict(size=11, color="red"))
        if target:
            fig.add_vline(x=target, line_color="#008000", line_width=1.5, line_dash="dash")
            fig.add_annotation(x=target, y=1.05, yref="paper", text="Target", showarrow=False,
                             font=dict(size=11, color="green"))
        if usl:
            fig.add_vline(x=usl, line_color="#000000", line_width=1.5, line_dash="dash")
            fig.add_annotation(x=usl, y=1.05, yref="paper", text="USL", showarrow=False,
                             font=dict(size=11, color="red"))

        fig.update_layout(
            title=dict(text=f"Process Capability Report for {col}", font=dict(size=16)),
            height=420, template="mckinsey",
            legend=dict(x=0.85, y=0.95, font=dict(size=10)),
            xaxis_title=col, yaxis_title="",
            yaxis=dict(showticklabels=False),
            margin=dict(t=80, b=40),
        )

        # ─── Results: Minitab-style layout ───
        # Process Data (left) + Capability (right)
        process_data = html.Div([
            html.H6("Process Data", className="fw-bold mb-2"),
            html.Table([
                html.Tr([html.Td("LSL", className="pe-3"), html.Td(f"{lsl}" if lsl else "—")]),
                html.Tr([html.Td("Target"), html.Td(f"{target}" if target else "—")]),
                html.Tr([html.Td("USL"), html.Td(f"{usl}" if usl else "—")]),
                html.Tr([html.Td("Sample Mean"), html.Td(f"{r.mean:.4f}")]),
                html.Tr([html.Td("Sample N"), html.Td(f"{r.n}")]),
                html.Tr([html.Td("StDev(Overall)"), html.Td(f"{r.std_overall:.6f}")]),
                html.Tr([html.Td("StDev(Within)"), html.Td(f"{r.std_within:.6f}")]),
            ], className="small"),
        ])

        overall_cap = html.Div([
            html.H6("Overall Capability", className="fw-bold mb-2"),
            html.Table([
                html.Tr([html.Td("Pp", className="pe-3"), html.Td(f"{r.pp:.2f}" if r.pp else "—")]),
                html.Tr([html.Td("PPL"), html.Td(f"{r.ppl:.2f}" if r.ppl else "—")]),
                html.Tr([html.Td("PPU"), html.Td(f"{r.ppu:.2f}" if r.ppu else "—")]),
                html.Tr([html.Td("Ppk"), html.Td(f"{r.ppk:.2f}" if r.ppk else "—")]),
                html.Tr([html.Td("Cpm"), html.Td(f"{r.cpm:.2f}" if r.cpm else "—")]),
            ], className="small"),
        ])

        within_cap = html.Div([
            html.H6("Potential (Within) Capability", className="fw-bold mb-2"),
            html.Table([
                html.Tr([html.Td("Cp", className="pe-3"), html.Td(f"{r.cp:.2f}" if r.cp else "—")]),
                html.Tr([html.Td("CPL"), html.Td(f"{r.cpl:.2f}" if r.cpl else "—")]),
                html.Tr([html.Td("CPU"), html.Td(f"{r.cpu:.2f}" if r.cpu else "—")]),
                html.Tr([html.Td("Cpk"), html.Td(f"{r.cpk:.2f}" if r.cpk else "—", className="fw-bold")]),
            ], className="small"),
        ])

        # PPM Performance table
        ppm_section = html.Div([
            html.H6("Performance", className="fw-bold mb-2 mt-3"),
            html.Table([
                html.Thead(html.Tr([html.Th(""), html.Th("Observed"), html.Th("Exp. Overall"), html.Th("Exp. Within")])),
                html.Tbody([
                    html.Tr([html.Td("PPM < LSL"), html.Td(f"{np.sum(data < lsl)/len(data)*1e6:.0f}" if lsl else "—"),
                             html.Td(f"{stats.norm.cdf(lsl, r.mean, r.std_overall)*1e6:.2f}" if lsl else "—"),
                             html.Td(f"{stats.norm.cdf(lsl, r.mean, r.std_within)*1e6:.2f}" if lsl else "—")]),
                    html.Tr([html.Td("PPM > USL"), html.Td(f"{np.sum(data > usl)/len(data)*1e6:.0f}" if usl else "—"),
                             html.Td(f"{stats.norm.sf(usl, r.mean, r.std_overall)*1e6:.2f}" if usl else "—"),
                             html.Td(f"{stats.norm.sf(usl, r.mean, r.std_within)*1e6:.2f}" if usl else "—")]),
                    html.Tr([html.Td("PPM Total"),
                             html.Td(f"{(np.sum(data < lsl) + np.sum(data > usl))/len(data)*1e6:.0f}" if (lsl and usl) else "—"),
                             html.Td(f"{r.ppm_overall:.2f}" if r.ppm_overall else "—"),
                             html.Td(f"{r.ppm_within:.2f}" if r.ppm_within else "—")]),
                ]),
            ], className="small table table-sm"),
        ])

        results_layout = dbc.Row([
            dbc.Col(process_data, width=4),
            dbc.Col([overall_cap, within_cap], width=4),
            dbc.Col(ppm_section, width=4),
        ], className="mt-3 p-3 border rounded bg-white")

        # Interpretation
        lines = []
        lines.append(f"n={r.n}, Mean={r.mean:.4f}")
        lines.append(f"σ_within={r.std_within:.6f}, σ_overall={r.std_overall:.6f}")
        lines.append(f"正态性: {'✅ 通过' if r.normality.is_normal else '❌ 非正态'} (SW p={r.normality.sw_p_value:.4f})")
        if r.transformation and r.transformation != "None":
            lines.append(f"变换: {r.transformation}" + (f", λ={r.lambda_boxcox:.4f}" if r.lambda_boxcox else ""))
        if r.cpk is not None:
            lines.append(f"\nCpk = {r.cpk:.3f}")
            if r.cpk >= 1.67: lines.append("  → 🟢 优秀 (Cpk ≥ 1.67)")
            elif r.cpk >= 1.33: lines.append("  → 🟢 良好 (Cpk ≥ 1.33)")
            elif r.cpk >= 1.0: lines.append("  → 🟡 勉强 (1.0 ≤ Cpk < 1.33)")
            else: lines.append("  → 🔴 不足 (Cpk < 1.0)，必须改进")
        return fig, results_layout, "\n".join(lines)
    except Exception as e:
        return go.Figure(), f"❌ {e}", ""
