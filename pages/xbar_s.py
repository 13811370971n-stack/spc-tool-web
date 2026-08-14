"""Xbar-S Control Chart Page."""
import dash
from dash import html, dcc, callback, Input, Output, State, no_update, dash_table
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd, numpy as np, base64, io
from core.xbar_s import calculate_xbar_s
from core.control_rules import get_all_violation_indices

dash.register_page(__name__, path="/xbar-s", name="Xbar-S", title="Xbar-S Chart")

layout = dbc.Container([
    html.H3("Xbar-S 控制图 (n>10)", className="mb-3"),
    dbc.Row([
        dbc.Col([
            dbc.Card([dbc.CardHeader("📂 数据导入"), dbc.CardBody([
                dcc.Upload(id="xs-upload", children=dbc.Button("上传", color="primary", className="w-100"), multiple=False),
                html.Div(id="xs-file-info", className="mt-2 small"),
                html.Hr(className="my-2"),
                dbc.Button("📋 加载Demo数据", id="xs-demo-btn", color="outline-secondary", size="sm", className="w-100"),
            ])], className="mb-3"),
            dbc.Card([dbc.CardHeader("列选择 (多选)"), dbc.CardBody([
                dcc.Dropdown(id="xs-cols", multi=True, placeholder="选择测量列..."),
            ])], className="mb-3"),
            dbc.Card([dbc.CardHeader("判异规则"), dbc.CardBody([
                dbc.Checklist(id="xs-tests", options=[{"label":f" T{i}","value":i} for i in range(1,9)], value=[1,2,3,4], inline=True, className="small"),
            ])], className="mb-3"),
            dbc.Button("▶ 分析", id="xs-analyze", color="primary", size="lg", className="w-100"),
        ], width=3),
        dbc.Col([
            dcc.Loading(dcc.Graph(id="xs-chart", style={"height":"500px"}), type="circle"),
            html.Pre(id="xs-interp", style={"whiteSpace":"pre-wrap","fontSize":"13px"}, className="mt-3 p-3 bg-light border rounded"),
        ], width=9),
    ]),
    dcc.Store(id="xs-store"),
], fluid=True)

@callback(Output("xs-store","data"),Output("xs-file-info","children"),Output("xs-cols","options"),Output("xs-cols","value"),
          Input("xs-upload","contents"),Input("xs-demo-btn","n_clicks"),State("xs-upload","filename"),prevent_initial_call=True)
def up(c,demo,f):
    from dash import ctx
    triggered = ctx.triggered_id
    sel_cols = None
    if triggered == "xs-demo-btn":
        from demo_loader import load_demo_data
        dj, config = load_demo_data("xbar-s")
        if not dj: return no_update,"❌",no_update,no_update
        df = pd.read_json(io.StringIO(dj), orient="split")
        f = config["file"]; sel_cols = config["data_cols"]
    elif c:
        d=base64.b64decode(c.split(",")[1])
        try: df=pd.read_csv(io.BytesIO(d)) if f.lower().endswith(".csv") else pd.read_excel(io.BytesIO(d),engine="xlrd" if f.lower().endswith(".xls") else "openpyxl")
        except Exception as e: return no_update,f"❌{e}",no_update,no_update
    else: return no_update,no_update,no_update,no_update
    nc=[c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    info = f"✓ {f}({len(df)}r)" + (" 📋" if triggered=="xs-demo-btn" else "")
    return df.to_json(orient="split"),info,[{"label":c,"value":c} for c in nc],sel_cols or no_update

@callback(Output("xs-chart","figure"),Output("xs-interp","children"),
          Input("xs-analyze","n_clicks"),State("xs-store","data"),State("xs-cols","value"),State("xs-tests","value"),prevent_initial_call=True)
def run(n,dj,cols,tests):
    if not dj or not cols or len(cols)<2: return go.Figure(),"选择≥2列"
    df=pd.read_json(io.StringIO(dj),orient="split")
    try:
        m=df[cols].dropna().values.astype(float)
        r=calculate_xbar_s(m,enabled_tests=tests or [1,2,3,4])
        fig=make_subplots(rows=2,cols=1,subplot_titles=("Xbar","S"),vertical_spacing=0.12)
        x=list(range(1,len(r.xbar)+1))
        fig.add_trace(go.Scatter(x=x,y=r.xbar,mode="lines+markers",name="Xbar",marker=dict(size=4)),row=1,col=1)
        fig.add_hline(y=r.xbar_limits.ucl,line_dash="dash",line_color="red",annotation_text=f"UCL={r.xbar_limits.ucl:.4f}",row=1,col=1)
        fig.add_hline(y=r.xbar_limits.cl,line_color="green",line_width=2,row=1,col=1)
        fig.add_hline(y=r.xbar_limits.lcl,line_dash="dash",line_color="red",row=1,col=1)
        fig.add_trace(go.Scatter(x=x,y=r.s,mode="lines+markers",name="S",marker=dict(size=4)),row=2,col=1)
        fig.add_hline(y=r.s_limits.ucl,line_dash="dash",line_color="red",annotation_text=f"UCL={r.s_limits.ucl:.4f}",row=2,col=1)
        fig.add_hline(y=r.s_limits.cl,line_color="green",line_width=2,row=2,col=1)
        if r.s_limits.lcl>0: fig.add_hline(y=r.s_limits.lcl,line_dash="dash",line_color="red",annotation_text=f"LCL={r.s_limits.lcl:.4f}",row=2,col=1)
        else: fig.add_hline(y=0,line_dash="dash",line_color="red",annotation_text="LCL=0",row=2,col=1)
        fig.update_layout(height=500,template="mckinsey",showlegend=True,legend=dict(orientation="h",y=-0.15))
        interp=f"{'✅ 受控' if r.in_control else '❌ 失控'}\nn={r.subgroup_size}, k={r.num_subgroups}\nσ_within={r.sigma_within:.6f}"
        return fig,interp
    except Exception as e: return go.Figure(),f"❌{e}"
