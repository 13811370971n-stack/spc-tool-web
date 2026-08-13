"""EWMA Control Chart Page."""
import dash
from dash import html, dcc, callback, Input, Output, State, no_update
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import pandas as pd, numpy as np, base64, io
from core.ewma import calculate_ewma

dash.register_page(__name__, path="/ewma", name="EWMA", title="EWMA Chart")

layout = dbc.Container([
    html.H3("EWMA 控制图", className="mb-3"),
    dbc.Row([
        dbc.Col([
            dbc.Card([dbc.CardHeader("📂 导入"), dbc.CardBody([
                dcc.Upload(id="ewma-upload", children=dbc.Button("上传", color="primary", className="w-100"), multiple=False),
                html.Div(id="ewma-info", className="mt-2 small"),
                html.Hr(className="my-2"),
                dbc.Button("📋 加载Demo数据", id="ewma-demo-btn", color="outline-secondary", size="sm", className="w-100"),
            ])], className="mb-3"),
            dbc.Card([dbc.CardHeader("设置"), dbc.CardBody([
                html.Label("数据列:"), dcc.Dropdown(id="ewma-col", placeholder="选择..."),
                html.Label("λ (平滑常数):", className="mt-2"),
                dcc.Slider(id="ewma-lambda", min=0.05, max=1.0, step=0.05, value=0.2, marks={0.1:"0.1",0.2:"0.2",0.5:"0.5",1.0:"1.0"}),
                html.Label("L (限宽系数):", className="mt-2"),
                dbc.Input(id="ewma-L", type="number", value=3.0, min=1, max=5, step=0.1),
            ])], className="mb-3"),
            dbc.Button("▶ 分析", id="ewma-analyze", color="primary", className="w-100"),
        ], width=3),
        dbc.Col([
            dcc.Loading(dcc.Graph(id="ewma-chart", style={"height":"400px"}), type="circle"),
            html.Pre(id="ewma-interp", style={"whiteSpace":"pre-wrap","fontSize":"13px"}, className="mt-3 p-3 bg-light border rounded"),
        ], width=9),
    ]),
    dcc.Store(id="ewma-store"),
], fluid=True)

@callback(Output("ewma-store","data"),Output("ewma-info","children"),Output("ewma-col","options"),Output("ewma-col","value"),
          Input("ewma-upload","contents"),Input("ewma-demo-btn","n_clicks"),State("ewma-upload","filename"),prevent_initial_call=True)
def up(c,demo,f):
    from dash import ctx
    triggered = ctx.triggered_id
    sel = None
    if triggered == "ewma-demo-btn":
        from demo_loader import load_demo_data
        dj, config = load_demo_data("ewma")
        if not dj: return no_update,"❌",no_update,no_update
        df = pd.read_json(io.StringIO(dj), orient="split")
        f = config["file"]; sel = config["data_col"]
    elif c:
        d=base64.b64decode(c.split(",")[1])
        try: df=pd.read_csv(io.BytesIO(d)) if f.lower().endswith(".csv") else pd.read_excel(io.BytesIO(d),engine="xlrd" if f.lower().endswith(".xls") else "openpyxl")
        except Exception as e: return no_update,f"❌{e}",no_update,no_update
    else: return no_update,no_update,no_update,no_update
    nc=[c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    return df.to_json(orient="split"),f"✓{f}({len(df)}r)"+(" 📋" if triggered=="ewma-demo-btn" else ""),[{"label":c,"value":c} for c in nc],sel or no_update

@callback(Output("ewma-chart","figure"),Output("ewma-interp","children"),
          Input("ewma-analyze","n_clicks"),State("ewma-store","data"),State("ewma-col","value"),
          State("ewma-lambda","value"),State("ewma-L","value"),prevent_initial_call=True)
def run(n,dj,col,lam,L):
    if not dj or not col: return go.Figure(),"选择列"
    df=pd.read_json(io.StringIO(dj),orient="split")
    try:
        data=df[col].dropna().values.astype(float)
        r=calculate_ewma(data,lambda_=lam or 0.2,L=float(L or 3.0))
        fig=go.Figure()
        x=list(range(1,r.num_observations+1))
        fig.add_trace(go.Scatter(x=x,y=r.ewma,mode="lines+markers",name="EWMA",marker=dict(size=4),line=dict(color="#051C2C")))
        fig.add_trace(go.Scatter(x=x,y=r.ucl,mode="lines",name="UCL",line=dict(color="red",dash="dash")))
        fig.add_trace(go.Scatter(x=x,y=r.lcl,mode="lines",name="LCL",line=dict(color="red",dash="dash")))
        fig.add_hline(y=r.cl,line_color="green",line_width=2,annotation_text=f"CL={r.cl:.4f}")
        if r.violations:
            fig.add_trace(go.Scatter(x=[x[i] for i in r.violations],y=[r.ewma[i] for i in r.violations],mode="markers",name="失控",marker=dict(color="red",size=10,symbol="circle-open",line=dict(width=2))))
        fig.update_layout(title=f"EWMA (λ={r.lambda_:.2f}, L={r.L:.1f})",height=400,template="mckinsey",legend=dict(orientation="h",y=-0.2))
        interp=f"{'✅ 受控' if r.in_control else '❌ 失控'}\nTarget={r.target:.4f}, σ={r.sigma:.4f}\n稳态UCL={r.ucl_ss:.4f}\n失控点数: {len(r.violations)}"
        return fig,interp
    except Exception as e: return go.Figure(),f"❌{e}"
