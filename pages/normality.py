"""Normality Test Page."""
import dash
from dash import html, dcc, callback, Input, Output, State, no_update, dash_table
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd, numpy as np, base64, io
from scipy import stats
from core.capability import test_normality

dash.register_page(__name__, path="/normality", name="正态性检验", title="Normality Test")

layout = dbc.Container([
    html.H3("正态性检验 (Normality Test)", className="mb-3"),
    dbc.Row([
        dbc.Col([
            dbc.Card([dbc.CardHeader("📂 导入"), dbc.CardBody([
                dcc.Upload(id="norm-upload", children=dbc.Button("上传", color="primary", className="w-100"), multiple=False),
                html.Div(id="norm-info", className="mt-2 small"),
            ])], className="mb-3"),
            dbc.Card([dbc.CardHeader("设置"), dbc.CardBody([
                html.Label("数据列:"), dcc.Dropdown(id="norm-col", placeholder="选择..."),
                html.Label("α:", className="mt-2"),
                dbc.Input(id="norm-alpha", type="number", value=0.05, min=0.001, max=0.2, step=0.01),
            ])], className="mb-3"),
            dbc.Button("▶ 检验", id="norm-analyze", color="primary", className="w-100"),
        ], width=3),
        dbc.Col([
            dcc.Loading(dcc.Graph(id="norm-chart", style={"height":"500px"}), type="circle"),
            html.Div(id="norm-results", className="mt-3"),
            html.Pre(id="norm-interp", style={"whiteSpace":"pre-wrap","fontSize":"13px"}, className="mt-3 p-3 bg-light border rounded"),
        ], width=9),
    ]),
    dcc.Store(id="norm-store"),
], fluid=True)

@callback(Output("norm-store","data"),Output("norm-info","children"),Output("norm-col","options"),
          Input("norm-upload","contents"),State("norm-upload","filename"),prevent_initial_call=True)
def up(c,f):
    if not c: return no_update,no_update,no_update
    d=base64.b64decode(c.split(",")[1])
    try:
        df=pd.read_csv(io.BytesIO(d)) if f.lower().endswith(".csv") else pd.read_excel(io.BytesIO(d),engine="xlrd" if f.lower().endswith(".xls") else "openpyxl")
        nc=[c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        return df.to_json(orient="split"),f"✓{f}({len(df)}r)",[{"label":c,"value":c} for c in nc]
    except Exception as e: return no_update,f"❌{e}",no_update

@callback(Output("norm-chart","figure"),Output("norm-results","children"),Output("norm-interp","children"),
          Input("norm-analyze","n_clicks"),State("norm-store","data"),State("norm-col","value"),State("norm-alpha","value"),prevent_initial_call=True)
def run(n,dj,col,alpha):
    if not dj or not col: return go.Figure(),"","选择列"
    df=pd.read_json(io.StringIO(dj),orient="split")
    alpha=float(alpha or 0.05)
    try:
        data=df[col].dropna().values.astype(float)
        nr=test_normality(data)
        ks_stat,ks_p=stats.kstest(data,'norm',args=(np.mean(data),np.std(data,ddof=1)))

        # 2x2 subplot: QQ, Histogram, Stats
        fig=make_subplots(rows=2,cols=2,subplot_titles=("Q-Q Plot","Histogram + Normal Fit","","描述统计"),
                          specs=[[{"type":"xy"},{"type":"xy"}],[{"type":"xy"},{"type":"table"}]])

        # QQ plot
        sorted_data=np.sort(data)
        n_pts=len(sorted_data)
        theoretical=stats.norm.ppf(np.linspace(0.5/n_pts,1-0.5/n_pts,n_pts))
        fig.add_trace(go.Scatter(x=theoretical,y=sorted_data,mode="markers",name="Q-Q",marker=dict(size=4,color="#3498DB")),row=1,col=1)
        # Fit line
        slope,intercept=np.polyfit(theoretical,sorted_data,1)
        fig.add_trace(go.Scatter(x=[theoretical[0],theoretical[-1]],y=[slope*theoretical[0]+intercept,slope*theoretical[-1]+intercept],mode="lines",name="Fit",line=dict(color="red")),row=1,col=1)

        # Histogram
        fig.add_trace(go.Histogram(x=data,nbinsx=int(np.sqrt(len(data))),name="Data",opacity=0.6,marker_color="#3498DB",histnorm="probability density"),row=1,col=2)
        x_range=np.linspace(data.min()-data.std(),data.max()+data.std(),100)
        fig.add_trace(go.Scatter(x=x_range,y=stats.norm.pdf(x_range,np.mean(data),np.std(data,ddof=1)),mode="lines",name="Normal",line=dict(color="red",width=2)),row=1,col=2)

        # Box-Cox profile (if data positive)
        if np.all(data>0):
            lambdas=np.linspace(-2,2,50)
            pvals=[]
            for lam in lambdas:
                t=np.log(data) if abs(lam)<0.01 else (data**lam-1)/lam
                _,p=stats.shapiro(t[:min(len(t),5000)])
                pvals.append(p)
            fig.add_trace(go.Scatter(x=lambdas,y=pvals,mode="lines",name="SW p-value",line=dict(color="#051C2C")),row=2,col=1)
            fig.add_hline(y=0.05,line_dash="dot",line_color="gray",row=2,col=1)
            best_lam=lambdas[np.argmax(pvals)]
            fig.add_vline(x=best_lam,line_dash="dash",line_color="red",annotation_text=f"λ={best_lam:.2f}",row=2,col=1)

        fig.update_layout(height=500,template="mckinsey",showlegend=False)
        fig.update_xaxes(title_text="Theoretical Quantiles",row=1,col=1)
        fig.update_yaxes(title_text="Sample Quantiles",row=1,col=1)
        fig.update_xaxes(title_text="λ",row=2,col=1)
        fig.update_yaxes(title_text="p-value",row=2,col=1)

        # Results table
        rows=[
            {"检验":"Anderson-Darling","统计量":f"{nr.ad_statistic:.4f}","结论":"✅ 正态" if nr.ad_is_normal else "❌ 非正态"},
            {"检验":"Shapiro-Wilk","统计量":f"{nr.sw_statistic:.4f} (p={nr.sw_p_value:.4f})","结论":"✅ 正态" if nr.sw_is_normal else "❌ 非正态"},
            {"检验":"Kolmogorov-Smirnov","统计量":f"{ks_stat:.4f} (p={ks_p:.4f})","结论":"✅ 正态" if ks_p>alpha else "❌ 非正态"},
        ]
        table=dash_table.DataTable(data=rows,columns=[{"name":c,"id":c} for c in ["检验","统计量","结论"]],
                                   style_cell={"textAlign":"center","fontSize":"13px"},style_header={"fontWeight":"bold","backgroundColor":"#3498DB","color":"white"})

        # Interpretation
        passed=sum([nr.ad_is_normal,nr.sw_is_normal,ks_p>alpha])
        lines=[f"{'✅ 正态 ('+str(passed)+'/3 通过)' if passed>=2 else '❌ 非正态'}"]
        lines.append(f"n={len(data)}, Mean={np.mean(data):.4f}, Std={np.std(data,ddof=1):.4f}")
        lines.append(f"Skewness={stats.skew(data):.3f}, Kurtosis={stats.kurtosis(data):.3f}")
        if passed<2:
            lines.append("\n建议: 考虑 Box-Cox 变换或检查离群值")

        return fig,table,"\n".join(lines)
    except Exception as e: return go.Figure(),"",f"❌{e}"
