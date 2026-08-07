"""NP, C, U Chart Pages."""
import dash
from dash import html, dcc, callback, Input, Output, State, no_update, dash_table
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import pandas as pd, numpy as np, base64, io
from core.attributes import calculate_np_chart, calculate_c_chart, calculate_u_chart
from core.control_rules import get_all_violation_indices

# ═══ NP Chart ═══

def _attr_layout(prefix, title, extra_fields=None):
    fields = [html.Label("不合格品/缺陷数列:"), dcc.Dropdown(id=f"{prefix}-defect-col", placeholder="选择...")]
    if extra_fields:
        fields.extend(extra_fields)
    return dbc.Container([
        html.H3(title, className="mb-3"),
        dbc.Row([
            dbc.Col([
                dbc.Card([dbc.CardHeader("📂 导入"), dbc.CardBody([
                    dcc.Upload(id=f"{prefix}-upload", children=dbc.Button("上传", color="primary", className="w-100"), multiple=False),
                    html.Div(id=f"{prefix}-info", className="mt-2 small"),
                ])], className="mb-3"),
                dbc.Card([dbc.CardHeader("列映射"), dbc.CardBody(fields)], className="mb-3"),
                dbc.Checklist(id=f"{prefix}-tests", options=[{"label":f" T{i}","value":i} for i in range(1,9)], value=[1,2,3,4], inline=True, className="small mb-3"),
                dbc.Button("▶ 分析", id=f"{prefix}-analyze", color="primary", className="w-100"),
            ], width=3),
            dbc.Col([
                dcc.Loading(dcc.Graph(id=f"{prefix}-chart", style={"height":"400px"}), type="circle"),
                html.Pre(id=f"{prefix}-interp", style={"whiteSpace":"pre-wrap","fontSize":"13px"}, className="mt-3 p-3 bg-light border rounded"),
            ], width=9),
        ]),
        dcc.Store(id=f"{prefix}-store"),
    ], fluid=True)

# NP layout
np_layout = _attr_layout("np", "NP 控制图 (不合格品数)", [
    html.Label("常数样本量 n:", className="mt-2"),
    dbc.Input(id="np-sample-size", type="number", value=150, min=1),
])

# C layout
c_layout = _attr_layout("c", "C 控制图 (缺陷数)")

# U layout
u_layout = _attr_layout("u", "U 控制图 (单位缺陷数)", [
    html.Label("样本量列:", className="mt-2"),
    dcc.Dropdown(id="u-size-col", placeholder="选择..."),
])

# Register pages with layouts
dash.register_page("np_chart", path="/np-chart", name="NP Chart", layout=np_layout)
dash.register_page("c_chart", path="/c-chart", name="C Chart", layout=c_layout)
dash.register_page("u_chart", path="/u-chart", name="U Chart", layout=u_layout)


def _upload_cb(prefix):
    @callback(Output(f"{prefix}-store","data"), Output(f"{prefix}-info","children"), Output(f"{prefix}-defect-col","options"),
              Input(f"{prefix}-upload","contents"), State(f"{prefix}-upload","filename"), prevent_initial_call=True)
    def cb(c,f):
        if not c: return no_update,no_update,no_update
        d=base64.b64decode(c.split(",")[1])
        try:
            df=pd.read_csv(io.BytesIO(d)) if f.endswith(".csv") else pd.read_excel(io.BytesIO(d),engine="xlrd" if f.endswith(".xls") else "openpyxl")
            return df.to_json(orient="split"),f"✓{f}({len(df)}r)",[{"label":c,"value":c} for c in df.columns]
        except Exception as e: return no_update,f"❌{e}",no_update
    return cb

_upload_cb("np")
_upload_cb("c")

# U chart needs extra dropdown
@callback(Output("u-store","data"), Output("u-info","children"), Output("u-defect-col","options"), Output("u-size-col","options"),
          Input("u-upload","contents"), State("u-upload","filename"), prevent_initial_call=True)
def u_upload(c,f):
    if not c: return no_update,no_update,no_update,no_update
    d=base64.b64decode(c.split(",")[1])
    try:
        df=pd.read_csv(io.BytesIO(d)) if f.endswith(".csv") else pd.read_excel(io.BytesIO(d),engine="xlrd" if f.endswith(".xls") else "openpyxl")
        opts=[{"label":c,"value":c} for c in df.columns]
        return df.to_json(orient="split"),f"✓{f}({len(df)}r)",opts,opts
    except Exception as e: return no_update,f"❌{e}",no_update,no_update


def _make_attr_chart(x, statistic, ucl, cl, lcl, constant_n, violations, title):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=statistic, mode="lines+markers", name="Data", marker=dict(size=5), line=dict(color="#2C3E50")))
    if constant_n:
        fig.add_hline(y=ucl[0], line_dash="dash", line_color="red", annotation_text=f"UCL={ucl[0]:.4f}")
        if lcl[0] > 0: fig.add_hline(y=lcl[0], line_dash="dash", line_color="red", annotation_text=f"LCL={lcl[0]:.4f}")
    else:
        fig.add_trace(go.Scatter(x=x, y=ucl, mode="lines", name="UCL", line=dict(color="red", dash="dash")))
        fig.add_trace(go.Scatter(x=x, y=lcl, mode="lines", name="LCL", line=dict(color="red", dash="dash")))
    fig.add_hline(y=cl, line_color="green", line_width=2, annotation_text=f"CL={cl:.4f}")
    if violations:
        vi = get_all_violation_indices(violations)
        fig.add_trace(go.Scatter(x=[x[i] for i in vi], y=[statistic[i] for i in vi], mode="markers", name="失控", marker=dict(color="red", size=10, symbol="circle-open", line=dict(width=2))))
    fig.update_layout(title=title, height=400, template="plotly_white", legend=dict(orientation="h", y=-0.2))
    return fig


@callback(Output("np-chart","figure"), Output("np-interp","children"),
          Input("np-analyze","n_clicks"), State("np-store","data"), State("np-defect-col","value"),
          State("np-sample-size","value"), State("np-tests","value"), prevent_initial_call=True)
def np_run(n, dj, col, sample_n, tests):
    if not dj or not col: return go.Figure(), "选择列"
    df = pd.read_json(io.StringIO(dj), orient="split")
    try:
        d = df[col].dropna().values.astype(float)
        r = calculate_np_chart(d, sample_size=int(sample_n or 150), enabled_tests=tests or [1,2,3,4])
        x = list(range(1, r.num_subgroups+1))
        fig = _make_attr_chart(x, r.statistic, r.ucl, r.cl, r.lcl, True, r.violations, "NP Chart")
        return fig, f"{'✅ 受控' if r.in_control else '❌ 失控'}\nnp̄={r.cl:.2f}, n={sample_n}"
    except Exception as e: return go.Figure(), f"❌{e}"


@callback(Output("c-chart","figure"), Output("c-interp","children"),
          Input("c-analyze","n_clicks"), State("c-store","data"), State("c-defect-col","value"),
          State("c-tests","value"), prevent_initial_call=True)
def c_run(n, dj, col, tests):
    if not dj or not col: return go.Figure(), "选择列"
    df = pd.read_json(io.StringIO(dj), orient="split")
    try:
        d = df[col].dropna().values.astype(float)
        r = calculate_c_chart(d, enabled_tests=tests or [1,2,3,4])
        x = list(range(1, r.num_subgroups+1))
        fig = _make_attr_chart(x, r.statistic, r.ucl, r.cl, r.lcl, True, r.violations, "C Chart")
        return fig, f"{'✅ 受控' if r.in_control else '❌ 失控'}\nc̄={r.cl:.2f}"
    except Exception as e: return go.Figure(), f"❌{e}"


@callback(Output("u-chart","figure"), Output("u-interp","children"),
          Input("u-analyze","n_clicks"), State("u-store","data"), State("u-defect-col","value"),
          State("u-size-col","value"), State("u-tests","value"), prevent_initial_call=True)
def u_run(n, dj, dcol, scol, tests):
    if not dj or not dcol or not scol: return go.Figure(), "选择列"
    df = pd.read_json(io.StringIO(dj), orient="split")
    try:
        defects = df[dcol].dropna().values.astype(float)
        sizes = df[scol].dropna().values.astype(float)
        ml = min(len(defects), len(sizes)); defects, sizes = defects[:ml], sizes[:ml]
        r = calculate_u_chart(defects, sizes, enabled_tests=tests or [1,2,3,4])
        x = list(range(1, r.num_subgroups+1))
        fig = _make_attr_chart(x, r.statistic, r.ucl, r.cl, r.lcl, r.constant_sample_size, r.violations, "U Chart")
        return fig, f"{'✅ 受控' if r.in_control else '❌ 失控'}\nū={r.cl:.4f}"
    except Exception as e: return go.Figure(), f"❌{e}"
