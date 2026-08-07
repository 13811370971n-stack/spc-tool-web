"""Z-MR Control Chart Page."""
import dash
from dash import html, dcc, callback, Input, Output, State, no_update
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd, numpy as np, base64, io
from core.zmr import calculate_zmr
from core.control_rules import get_all_violation_indices

dash.register_page(__name__, path="/zmr", name="Z-MR", title="Z-MR Chart")

layout = dbc.Container([
    html.H3("Z-MR 控制图 (短期生产)", className="mb-3"),
    dbc.Row([
        dbc.Col([
            dbc.Card([dbc.CardHeader("📂 导入"), dbc.CardBody([
                dcc.Upload(id="zmr-upload", children=dbc.Button("上传", color="primary", className="w-100"), multiple=False),
                html.Div(id="zmr-info", className="mt-2 small"),
            ])], className="mb-3"),
            dbc.Card([dbc.CardHeader("列映射"), dbc.CardBody([
                html.Label("测量值列:"), dcc.Dropdown(id="zmr-data-col", placeholder="选择..."),
                html.Label("零件类型列:", className="mt-2"), dcc.Dropdown(id="zmr-type-col", placeholder="选择..."),
            ])], className="mb-3"),
            dbc.Button("▶ 分析", id="zmr-analyze", color="primary", className="w-100"),
        ], width=3),
        dbc.Col([
            dcc.Loading(dcc.Graph(id="zmr-chart", style={"height":"500px"}), type="circle"),
            html.Pre(id="zmr-interp", style={"whiteSpace":"pre-wrap","fontSize":"13px"}, className="mt-3 p-3 bg-light border rounded"),
        ], width=9),
    ]),
    dcc.Store(id="zmr-store"),
], fluid=True)

@callback(Output("zmr-store","data"),Output("zmr-info","children"),Output("zmr-data-col","options"),Output("zmr-type-col","options"),
          Input("zmr-upload","contents"),State("zmr-upload","filename"),prevent_initial_call=True)
def up(c,f):
    if not c: return no_update,no_update,no_update,no_update
    d=base64.b64decode(c.split(",")[1])
    try:
        df=pd.read_csv(io.BytesIO(d)) if f.endswith(".csv") else pd.read_excel(io.BytesIO(d),engine="xlrd" if f.endswith(".xls") else "openpyxl")
        opts=[{"label":c,"value":c} for c in df.columns]
        return df.to_json(orient="split"),f"✓{f}({len(df)}r)",opts,opts
    except Exception as e: return no_update,f"❌{e}",no_update,no_update

@callback(Output("zmr-chart","figure"),Output("zmr-interp","children"),
          Input("zmr-analyze","n_clicks"),State("zmr-store","data"),State("zmr-data-col","value"),State("zmr-type-col","value"),prevent_initial_call=True)
def run(n,dj,dcol,tcol):
    if not dj or not dcol or not tcol: return go.Figure(),"选择列"
    df=pd.read_json(io.StringIO(dj),orient="split")
    try:
        subset=df[[dcol,tcol]].dropna()
        data=subset[dcol].values.astype(float)
        types=subset[tcol].values.astype(str)
        r=calculate_zmr(data,types,enabled_tests=[1,2,3,4])

        fig=make_subplots(rows=2,cols=1,subplot_titles=("Z 标准化图","Z-MR 移动极差"),vertical_spacing=0.12)
        x=list(range(1,r.num_observations+1))
        x_mr=list(range(2,len(r.z_mr)+2))

        # Color by type
        unique_types=list(r.type_params.keys())
        import plotly.express as px
        colors=px.colors.qualitative.Set1
        for i,t in enumerate(unique_types):
            mask=np.array([types[j]==t for j in range(len(types))])
            idx_t=np.where(mask)[0]
            fig.add_trace(go.Scatter(x=[x[j] for j in idx_t],y=[r.z[j] for j in idx_t],mode="markers",name=f"Type {t}",
                                      marker=dict(color=colors[i%len(colors)],size=7)),row=1,col=1)
        fig.add_trace(go.Scatter(x=x,y=r.z,mode="lines",name="Z",line=dict(color="gray",width=0.8),showlegend=False),row=1,col=1)
        fig.add_hline(y=3,line_dash="dash",line_color="red",annotation_text="UCL=+3",row=1,col=1)
        fig.add_hline(y=0,line_color="green",line_width=2,row=1,col=1)
        fig.add_hline(y=-3,line_dash="dash",line_color="red",annotation_text="LCL=-3",row=1,col=1)

        fig.add_trace(go.Scatter(x=x_mr,y=r.z_mr,mode="lines+markers",name="Z-MR",marker=dict(size=4),line=dict(color="#2C3E50")),row=2,col=1)
        fig.add_hline(y=r.zmr_limits.ucl,line_dash="dash",line_color="red",annotation_text=f"UCL={r.zmr_limits.ucl:.3f}",row=2,col=1)
        fig.add_hline(y=r.zmr_limits.cl,line_color="green",line_width=2,row=2,col=1)

        fig.update_layout(height=500,template="plotly_white",legend=dict(orientation="h",y=-0.15))

        lines=[f"{'✅ 受控' if r.in_control else '❌ 失控'}",f"类型数: {r.num_types}, 观测数: {r.num_observations}",""]
        for t,p in r.type_params.items():
            lines.append(f"  {t}: target={p['target']:.2f}, σ={p['sigma']:.4f}")
        return fig,"\n".join(lines)
    except Exception as e: return go.Figure(),f"❌{e}"
