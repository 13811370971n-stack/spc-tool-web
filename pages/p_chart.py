"""
P Chart Page.
"""

import dash
from dash import html, dcc, callback, Input, Output, State, no_update, dash_table
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import base64, io

from core.attributes import calculate_p_chart
from core.control_rules import get_all_violation_indices

dash.register_page(__name__, path="/p-chart", name="P Chart", title="P Chart")

layout = dbc.Container([
    html.H3("P 控制图 (不合格品率)", className="mb-3"),
    dbc.Row([
        dbc.Col([
            dbc.Card([dbc.CardHeader("📂 数据导入"), dbc.CardBody([
                dcc.Upload(id="p-upload", children=dbc.Button("上传 CSV/Excel", color="primary", className="w-100"), multiple=False),
                html.Div(id="p-file-info", className="mt-2 text-muted small"),
                html.Hr(className="my-2"),
                dbc.Button("📋 加载Demo数据", id="p-demo-btn", color="outline-secondary", size="sm", className="w-100"),
            ])], className="mb-3"),
            dbc.Card([dbc.CardHeader("列映射"), dbc.CardBody([
                html.Label("不合格品数列:"), dcc.Dropdown(id="p-defect-col", placeholder="选择..."),
                html.Label("样本量列:", className="mt-2"), dcc.Dropdown(id="p-size-col", placeholder="选择..."),
            ])], className="mb-3"),
            dbc.Card([dbc.CardHeader("判异规则"), dbc.CardBody([
                dbc.Checklist(id="p-tests", options=[{"label": f" Test {i}", "value": i} for i in range(1, 9)], value=[1,2,3,4], inline=True, className="small"),
            ])], className="mb-3"),
            dbc.Button("▶ 分析", id="p-analyze", color="primary", size="lg", className="w-100"),
        ], width=3),
        dbc.Col([
            dcc.Loading(dcc.Graph(id="p-chart", style={"height": "400px"}), type="circle"),
            html.Div(id="p-results", className="mt-3"),
            dbc.Card([dbc.CardHeader("📋 分析解读"), dbc.CardBody(html.Pre(id="p-interpretation", style={"whiteSpace": "pre-wrap", "fontSize": "13px"}))], className="mt-3"),
        ], width=9),
    ]),
    dcc.Store(id="p-data-store"),
], fluid=True)


@callback(Output("p-data-store","data"), Output("p-file-info","children"), Output("p-defect-col","options"), Output("p-defect-col","value"), Output("p-size-col","options"), Output("p-size-col","value"),
          Input("p-upload","contents"), Input("p-demo-btn","n_clicks"), State("p-upload","filename"), prevent_initial_call=True)
def on_upload(contents, demo_clicks, filename):
    from dash import ctx
    triggered = ctx.triggered_id
    sel_defect = sel_size = None

    if triggered == "p-demo-btn":
        from demo_loader import load_demo_data
        data_json, config = load_demo_data("p-chart")
        if not data_json: return no_update, "❌", no_update, no_update, no_update, no_update
        df = pd.read_json(io.StringIO(data_json), orient="split")
        filename = config["file"]
        sel_defect = config["defect_col"]
        sel_size = config["size_col"]
    elif contents:
        decoded = base64.b64decode(contents.split(",")[1])
        try:
            df = pd.read_csv(io.BytesIO(decoded)) if filename.lower().endswith(".csv") else pd.read_excel(io.BytesIO(decoded), engine="xlrd" if filename.lower().endswith(".xls") else "openpyxl")
        except Exception as e:
            return no_update, f"❌ {e}", no_update, no_update, no_update, no_update
    else:
        return no_update, no_update, no_update, no_update, no_update, no_update

    data_json = df.to_json(orient="split")
    opts = [{"label":c,"value":c} for c in df.columns]
    info = f"✓ {filename} ({len(df)} rows)" + (" 📋 Demo" if triggered == "p-demo-btn" else "")
    return data_json, info, opts, sel_defect or no_update, opts, sel_size or no_update


@callback(Output("p-chart","figure"), Output("p-results","children"), Output("p-interpretation","children"),
          Input("p-analyze","n_clicks"), State("p-data-store","data"), State("p-defect-col","value"),
          State("p-size-col","value"), State("p-tests","value"), prevent_initial_call=True)
def on_analyze(n, data_json, defect_col, size_col, tests):
    if not data_json or not defect_col or not size_col: return go.Figure(), "请选择列", ""
    df = pd.read_json(io.StringIO(data_json), orient="split")
    try:
        defectives = df[defect_col].dropna().values.astype(float)
        sizes = df[size_col].dropna().values.astype(float)
        min_len = min(len(defectives), len(sizes))
        defectives, sizes = defectives[:min_len], sizes[:min_len]

        r = calculate_p_chart(defectives, sizes, enabled_tests=tests or [1,2,3,4])

        fig = go.Figure()
        x = list(range(1, r.num_subgroups+1))
        fig.add_trace(go.Scatter(x=x, y=r.statistic, mode="lines+markers", name="p", line=dict(color="#051C2C"), marker=dict(size=5)))

        if r.constant_sample_size:
            fig.add_hline(y=r.ucl[0], line_dash="dash", line_color="red", annotation_text=f"UCL={r.ucl[0]:.4f}")
            fig.add_hline(y=r.lcl[0], line_dash="dash", line_color="red", annotation_text=f"LCL={r.lcl[0]:.4f}")
        else:
            fig.add_trace(go.Scatter(x=x, y=r.ucl, mode="lines", name="UCL", line=dict(color="red", dash="dash", width=1)))
            fig.add_trace(go.Scatter(x=x, y=r.lcl, mode="lines", name="LCL", line=dict(color="red", dash="dash", width=1)))
        fig.add_hline(y=r.cl, line_color="green", line_width=2, annotation_text=f"CL={r.cl:.4f}")

        if r.violations:
            vi = get_all_violation_indices(r.violations)
            fig.add_trace(go.Scatter(x=[x[i] for i in vi], y=[r.statistic[i] for i in vi], mode="markers", name="失控", marker=dict(color="red", size=10, symbol="circle-open", line=dict(width=2))))

        fig.update_layout(title="P Chart", height=400, template="mckinsey", legend=dict(orientation="h", y=-0.2))
        fig.update_xaxes(title_text="子组号")
        fig.update_yaxes(title_text="p (不合格品率)")

        table = dash_table.DataTable(
            data=[{"指标":"p̄","值":f"{r.cl:.4f} ({r.cl*100:.2f}%)"},{"指标":"n̄","值":f"{r.avg_sample_size:.0f}"},{"指标":"常数n","值":"是" if r.constant_sample_size else "否"},{"指标":"状态","值":"✅ 受控" if r.in_control else "❌ 失控"}],
            columns=[{"name":"指标","id":"指标"},{"name":"值","id":"值"}],
            style_cell={"textAlign":"center","fontSize":"13px"}, style_header={"fontWeight":"bold","backgroundColor":"#3498DB","color":"white"})

        lines = ["✅ 过程受控" if r.in_control else "❌ 过程失控"]
        lines.append(f"p̄ = {r.cl:.4f} ({r.cl*100:.2f}%)")
        if r.violations:
            for t, idx in r.violations.items():
                lines.append(f"  判异{t}: 子组 {[i+1 for i in idx[:10]]}")
        return fig, table, "\n".join(lines)
    except Exception as e:
        return go.Figure(), f"❌ {e}", ""
