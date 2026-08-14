"""
Xbar-R Control Chart Page.
Dash page with interactive Plotly charts.
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

from core.xbar_r import calculate_xbar_r, XbarRResult
from core.control_rules import get_all_violation_indices
from core.llm_integration import load_config, enhance_interpretation

dash.register_page(__name__, path="/xbar-r", name="Xbar-R", title="Xbar-R Control Chart")

# ─── Rule descriptions ─────────────────────────────────────────────────────────
RULE_DESCRIPTIONS = {
    1: "1点超出3σ控制限",
    2: "连续9点在中心线同侧",
    3: "连续6点递增或递减",
    4: "连续14点交替升降",
    5: "3点中2点超过2σ(同侧)",
    6: "5点中4点超过1σ(同侧)",
    7: "连续15点在1σ内(层化)",
    8: "连续8点在1σ外(两侧)",
}

RULE_CAUSES = {
    1: "原材料批次异常、设备突发故障、操作失误、测量错误",
    2: "刀具磨损、设备漂移、原材料特性渐变、环境温度变化",
    3: "刀具逐渐磨损、化学浓度消耗、设备热膨胀、操作员疲劳",
    4: "两台设备交替使用、两种原料交替、过度调整",
    5: "原料批间差异、操作方法不一致、设备参数波动",
    6: "轻微设备漂移、环境条件缓慢变化、人员习惯性偏差",
    7: "数据来自多个不同总体、计算错误、控制限设置不当",
    8: "两种不同规格材料混合、两组不同设置设备混合数据",
}


# ─── Layout ────────────────────────────────────────────────────────────────────
layout = dbc.Container([
    html.H3("Xbar-R 控制图", className="mb-3"),

    dbc.Row([
        # Left: controls
        dbc.Col([
            # File upload
            dbc.Card([
                dbc.CardHeader("📂 数据导入"),
                dbc.CardBody([
                    dcc.Upload(
                        id="xbar-r-upload",
                        children=dbc.Button("点击上传 CSV/Excel", color="primary", className="w-100"),
                        multiple=False,
                    ),
                    html.Div(id="xbar-r-file-info", className="mt-2 text-muted small"),
                    html.Hr(className="my-2"),
                    dbc.Button("📋 加载Demo数据", id="xbar-r-demo-btn", color="outline-secondary", size="sm", className="w-100"),
                ]),
            ], className="mb-3"),

            # Column selection
            dbc.Card([
                dbc.CardHeader("列选择"),
                dbc.CardBody([
                    html.Label("测量值列 (多选):"),
                    dcc.Dropdown(id="xbar-r-data-cols", multi=True, placeholder="选择列..."),
                    html.Label("子组列 (可选):", className="mt-2"),
                    dcc.Dropdown(id="xbar-r-subgroup-col", placeholder="自动"),
                ]),
            ], className="mb-3"),

            # Parameters
            dbc.Card([
                dbc.CardHeader("参数设置"),
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([html.Label("USL:"), dbc.Input(id="xbar-r-usl", type="number", placeholder="N/A")], width=6),
                        dbc.Col([html.Label("LSL:"), dbc.Input(id="xbar-r-lsl", type="number", placeholder="N/A")], width=6),
                    ]),
                    html.Label("判异规则:", className="mt-2"),
                    dbc.Checklist(
                        id="xbar-r-tests",
                        options=[{"label": f" Test {i}", "value": i} for i in range(1, 9)],
                        value=[1, 2, 3, 4],
                        inline=True,
                        className="small",
                    ),
                ]),
            ], className="mb-3"),

            # Analyze button
            dbc.Button("▶ 分析", id="xbar-r-analyze", color="primary", size="lg", className="w-100 mb-2"),
            dbc.Button("🤖 AI 增强解读", id="xbar-r-ai", color="secondary", size="sm", className="w-100"),

        ], width=3),

        # Right: results
        dbc.Col([
            # Data preview
            html.Div(id="xbar-r-preview", className="mb-3"),

            # Chart
            dcc.Loading(
                dcc.Graph(id="xbar-r-chart", style={"height": "500px"}),
                type="circle",
            ),

            # Results
            html.Div(id="xbar-r-results", className="mt-3"),

            # Interpretation
            dbc.Card([
                dbc.CardHeader("📋 分析解读"),
                dbc.CardBody(
                    html.Pre(id="xbar-r-interpretation", style={"whiteSpace": "pre-wrap", "fontSize": "13px"}),
                ),
            ], className="mt-3"),

            # AI + Download
            dbc.Card([
                dbc.CardHeader("🤖 AI & 报告下载"),
                dbc.CardBody([
                    dbc.Button("🤖 AI 增强解读", id="xbar-r-ai-btn", color="secondary", className="w-100 mb-2"),
                    dcc.Loading(html.Div(id="xbar-r-ai-output", className="small mt-2"), type="dot"),
                    html.Hr(),
                    html.Label("下载报告:"),
                    dbc.ButtonGroup([
                        dbc.Button("📄 Word", id="xbar-r-dl-word", color="success", size="sm", outline=True),
                        dbc.Button("📊 Excel", id="xbar-r-dl-excel", color="success", size="sm", outline=True),
                    ], className="w-100"),
                    dcc.Download(id="xbar-r-download"),
                ]),
            ], className="mt-3"),
        ], width=9),
    ]),

    # Hidden store for data
    dcc.Store(id="xbar-r-data-store"),
    dcc.Store(id="xbar-r-analysis-summary"),
], fluid=True)


# ─── Callbacks ─────────────────────────────────────────────────────────────────

@callback(
    Output("xbar-r-data-store", "data"),
    Output("xbar-r-file-info", "children"),
    Output("xbar-r-data-cols", "options"),
    Output("xbar-r-data-cols", "value"),
    Output("xbar-r-subgroup-col", "options"),
    Output("xbar-r-preview", "children"),
    Input("xbar-r-upload", "contents"),
    Input("xbar-r-demo-btn", "n_clicks"),
    State("xbar-r-upload", "filename"),
    prevent_initial_call=True,
)
def on_upload(contents, demo_clicks, filename):
    """Handle file upload or demo data load."""
    from dash import ctx
    triggered = ctx.triggered_id

    df = None
    selected_cols = None

    if triggered == "xbar-r-demo-btn":
        # Load demo data
        from demo_loader import load_demo_data
        data_json, config = load_demo_data("xbar-r")
        if data_json is None:
            return no_update, "❌ Demo数据文件不存在", no_update, no_update, no_update, no_update
        df = pd.read_json(io.StringIO(data_json), orient="split")
        filename = config["file"]
        selected_cols = config["data_cols"]
    elif contents:
        content_type, content_string = contents.split(",")
        decoded = base64.b64decode(content_string)
        try:
            if filename.lower().endswith(".csv"):
                df = pd.read_csv(io.BytesIO(decoded))
            elif filename.lower().endswith((".xls", ".xlsx")):
                engine = "xlrd" if filename.lower().endswith(".xls") else "openpyxl"
                df = pd.read_excel(io.BytesIO(decoded), engine=engine)
            else:
                return no_update, "❌ 不支持的文件格式", no_update, no_update, no_update, no_update
        except Exception as e:
            return no_update, f"❌ 导入错误: {e}", no_update, no_update, no_update, no_update
    else:
        return no_update, no_update, no_update, no_update, no_update, no_update

    # Process dataframe
    data_json = df.to_json(date_format="iso", orient="split")
    info = f"✓ {filename} ({len(df)} rows × {len(df.columns)} cols)"
    if triggered == "xbar-r-demo-btn":
        info += " 📋 Demo"

    numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    col_options = [{"label": c, "value": c} for c in numeric_cols]
    all_options = [{"label": c, "value": c} for c in df.columns]

    preview = dash_table.DataTable(
        data=df.head(5).to_dict("records"),
        columns=[{"name": c, "id": c} for c in df.columns],
        style_table={"overflowX": "auto", "fontSize": "12px"},
        style_cell={"textAlign": "center", "padding": "4px"},
        style_header={"fontWeight": "bold", "backgroundColor": "#f8f9fa"},
    )

    # Auto-select demo columns or None
    col_value = selected_cols if selected_cols else no_update

    return data_json, info, col_options, col_value, all_options, preview


@callback(
    Output("xbar-r-chart", "figure"),
    Output("xbar-r-results", "children"),
    Output("xbar-r-interpretation", "children"),
    Output("xbar-r-analysis-summary", "data"),
    Input("xbar-r-analyze", "n_clicks"),
    State("xbar-r-data-store", "data"),
    State("xbar-r-data-cols", "value"),
    State("xbar-r-subgroup-col", "value"),
    State("xbar-r-usl", "value"),
    State("xbar-r-lsl", "value"),
    State("xbar-r-tests", "value"),
    prevent_initial_call=True,
)
def on_analyze(n_clicks, data_json, data_cols, subgroup_col, usl, lsl, tests):
    """Run Xbar-R analysis."""
    if not data_json or not data_cols:
        return go.Figure(), "请先导入数据并选择列", "等待分析...", None

    df = pd.read_json(io.StringIO(data_json), orient="split")

    try:
        # Build matrix from selected columns
        if len(data_cols) >= 2:
            matrix = df[data_cols].dropna().values.astype(float)
        elif subgroup_col:
            # Long format → pivot
            col = data_cols[0]
            groups = df.groupby(subgroup_col)[col].apply(list)
            max_n = max(len(g) for g in groups)
            matrix = np.full((len(groups), max_n), np.nan)
            for i, vals in enumerate(groups):
                matrix[i, :len(vals)] = vals
        else:
            return go.Figure(), "请选择多列或指定子组列", ""

        if matrix.shape[1] < 2:
            return go.Figure(), "子组大小 ≥ 2", ""
        if matrix.shape[1] > 10:
            return go.Figure(), f"n={matrix.shape[1]} > 10, 请使用 Xbar-S", ""

        # Run analysis
        result = calculate_xbar_r(
            data=matrix,
            enabled_tests=tests or [1, 2, 3, 4],
            usl=usl if usl else None,
            lsl=lsl if lsl else None,
        )

        # Generate interactive Plotly chart
        fig = _create_xbar_r_figure(result)

        # Results table
        results_table = _create_results_table(result)

        # Interpretation
        interpretation = _create_interpretation(result)

        # Summary for AI/download
        import json
        summary = {
            "chart_type": "Xbar-R",
            "in_control": bool(result.in_control),
            "violations": {str(k): [i+1 for i in v[:10]] for k, v in result.xbar_violations.items()},
            "limits": {"Xbar UCL": f"{result.xbar_limits.ucl:.4f}", "Xbar CL": f"{result.xbar_limits.cl:.4f}",
                       "Xbar LCL": f"{result.xbar_limits.lcl:.4f}", "R UCL": f"{result.r_limits.ucl:.4f}", "R CL": f"{result.r_limits.cl:.4f}"},
            "sigma_within": float(result.sigma_within),
            "sigma_overall": float(result.sigma_overall),
            "data_summary": f"n={result.subgroup_size}, k={result.num_subgroups}",
        }
        if result.capability:
            summary["capability"] = {k: f"{v:.4f}" for k, v in result.capability.items()}

        return fig, results_table, interpretation, json.dumps(summary)

    except Exception as e:
        return go.Figure(), f"❌ 分析错误: {e}", "", None


def _create_xbar_r_figure(result: XbarRResult) -> go.Figure:
    """Create interactive Plotly Xbar-R chart."""
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=("Xbar 均值图", "R 极差图"),
        vertical_spacing=0.12,
    )

    x = list(range(1, len(result.xbar) + 1))

    # ─── Xbar Chart ───
    # Data
    fig.add_trace(go.Scatter(
        x=x, y=result.xbar, mode="lines+markers",
        name="Xbar", line=dict(color="#051C2C", width=1.5),
        marker=dict(size=5),
    ), row=1, col=1)

    # Control limits
    fig.add_hline(y=result.xbar_limits.ucl, line_dash="dash", line_color="red",
                  annotation_text=f"UCL={result.xbar_limits.ucl:.4f}", row=1, col=1)
    fig.add_hline(y=result.xbar_limits.cl, line_color="green", line_width=2,
                  annotation_text=f"CL={result.xbar_limits.cl:.4f}", row=1, col=1)
    fig.add_hline(y=result.xbar_limits.lcl, line_dash="dash", line_color="red",
                  annotation_text=f"LCL={result.xbar_limits.lcl:.4f}", row=1, col=1)

    # Violations
    if result.xbar_violations:
        all_v = get_all_violation_indices(result.xbar_violations)
        vx = [x[i] for i in all_v if i < len(x)]
        vy = [result.xbar[i] for i in all_v if i < len(result.xbar)]
        fig.add_trace(go.Scatter(
            x=vx, y=vy, mode="markers", name="失控点 (Xbar)",
            marker=dict(color="red", size=10, symbol="circle-open", line=dict(width=2)),
        ), row=1, col=1)

    # ─── R Chart ───
    fig.add_trace(go.Scatter(
        x=x, y=result.r, mode="lines+markers",
        name="R", line=dict(color="#051C2C", width=1.5),
        marker=dict(size=5),
    ), row=2, col=1)

    fig.add_hline(y=result.r_limits.ucl, line_dash="dash", line_color="red",
                  annotation_text=f"UCL={result.r_limits.ucl:.4f}", row=2, col=1)
    fig.add_hline(y=result.r_limits.cl, line_color="green", line_width=2,
                  annotation_text=f"CL={result.r_limits.cl:.4f}", row=2, col=1)
    fig.add_hline(y=result.r_limits.lcl, line_dash="dash", line_color="red",
                  annotation_text=f"LCL={result.r_limits.lcl:.4f}", row=2, col=1)

    # R violations
    if result.r_violations:
        all_v = get_all_violation_indices(result.r_violations)
        vx = [x[i] for i in all_v if i < len(x)]
        vy = [result.r[i] for i in all_v if i < len(result.r)]
        fig.add_trace(go.Scatter(
            x=vx, y=vy, mode="markers", name="失控点 (R)",
            marker=dict(color="red", size=10, symbol="circle-open", line=dict(width=2)),
        ), row=2, col=1)

    fig.update_layout(
        height=500,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.15),
        margin=dict(l=60, r=30, t=60, b=60),
        template="mckinsey",
    )
    fig.update_xaxes(title_text="子组号", row=2, col=1)

    return fig


def _create_results_table(result: XbarRResult):
    """Create results summary as HTML table."""
    rows = [
        {"图表": "Xbar 均值图", "UCL": f"{result.xbar_limits.ucl:.4f}",
         "CL": f"{result.xbar_limits.cl:.4f}", "LCL": f"{result.xbar_limits.lcl:.4f}",
         "状态": "✅ 受控" if result.xbar_in_control else "❌ 失控"},
        {"图表": "R 极差图", "UCL": f"{result.r_limits.ucl:.4f}",
         "CL": f"{result.r_limits.cl:.4f}", "LCL": f"{result.r_limits.lcl:.4f}",
         "状态": "✅ 受控" if result.r_in_control else "❌ 失控"},
    ]
    df = pd.DataFrame(rows)

    return dash_table.DataTable(
        data=df.to_dict("records"),
        columns=[{"name": c, "id": c} for c in df.columns],
        style_cell={"textAlign": "center", "padding": "8px", "fontSize": "13px"},
        style_header={"fontWeight": "bold", "backgroundColor": "#3498DB", "color": "white"},
        style_data_conditional=[
            {"if": {"filter_query": '{状态} contains "失控"'}, "backgroundColor": "#FADBD8"},
            {"if": {"filter_query": '{状态} contains "受控"'}, "backgroundColor": "#D5F5E3"},
        ],
    )


def _create_interpretation(result: XbarRResult) -> str:
    """Generate rich interpretation text."""
    lines = []

    if result.in_control:
        lines.append("═══════════════════════════════════════")
        lines.append("✅ 过程受控 (In Statistical Control)")
        lines.append("═══════════════════════════════════════")
        lines.append("所有子组均在控制限内，未触发判异规则。")
    else:
        lines.append("═══════════════════════════════════════")
        lines.append("❌ 过程失控 (Out of Control)")
        lines.append("═══════════════════════════════════════\n")

        if result.xbar_violations:
            lines.append("【Xbar 均值图判异】")
            for test_num, indices in sorted(result.xbar_violations.items()):
                desc = RULE_DESCRIPTIONS.get(test_num, f"Test {test_num}")
                cause = RULE_CAUSES.get(test_num, "")
                subgroups = [i + 1 for i in indices]
                lines.append(f"  ⚠️ 判异{test_num}: {desc}")
                lines.append(f"     失控子组: {subgroups[:10]}{'...' if len(subgroups)>10 else ''}")
                lines.append(f"     可能原因: {cause}\n")

        if result.r_violations:
            lines.append("【R 极差图判异】")
            for test_num, indices in sorted(result.r_violations.items()):
                desc = RULE_DESCRIPTIONS.get(test_num, f"Test {test_num}")
                cause = RULE_CAUSES.get(test_num, "")
                subgroups = [i + 1 for i in indices]
                lines.append(f"  ⚠️ 判异{test_num}: {desc}")
                lines.append(f"     失控子组: {subgroups[:10]}\n")

    # Statistics
    lines.append("\n─── 统计摘要 ───")
    lines.append(f"n={result.subgroup_size}, k={result.num_subgroups}")
    lines.append(f"Xbar={result.xbar_limits.cl:.6f}, Rbar={result.r_limits.cl:.6f}")
    lines.append(f"σ_within={result.sigma_within:.6f}, σ_overall={result.sigma_overall:.6f}")

    if result.capability:
        cap = result.capability
        lines.append("\n─── 过程能力 ───")
        if "Cpk" in cap:
            lines.append(f"Cpk={cap['Cpk']:.3f}  Ppk={cap.get('Ppk','N/A'):.3f}")

    return "\n".join(lines)


# ─── AI Callback ───────────────────────────────────────────────────────────────

@callback(
    Output("xbar-r-ai-output", "children"),
    Input("xbar-r-ai-btn", "n_clicks"),
    State("xbar-r-analysis-summary", "data"),
    prevent_initial_call=True,
)
def on_ai(n_clicks, summary_json):
    import json
    if not summary_json:
        return html.Div("⚠️ 请先运行分析", className="text-warning")
    config = load_config()
    if not config.enabled:
        return html.Div("⚠️ AI 未启用。配置 ~/.spc-tool/llm_config.json", className="text-warning")
    try:
        summary = json.loads(summary_json)
        result = enhance_interpretation(summary, config)
        return html.Pre(result, style={"whiteSpace": "pre-wrap", "fontSize": "12px", "maxHeight": "300px", "overflowY": "auto"})
    except Exception as e:
        return html.Div(f"❌ AI 错误: {e}", className="text-danger")


# ─── Download Callbacks ────────────────────────────────────────────────────────

@callback(
    Output("xbar-r-download", "data"),
    Input("xbar-r-dl-word", "n_clicks"),
    Input("xbar-r-dl-excel", "n_clicks"),
    State("xbar-r-analysis-summary", "data"),
    prevent_initial_call=True,
)
def on_download(n_word, n_excel, summary_json):
    from dash import ctx
    import json
    if not summary_json:
        return no_update
    summary = json.loads(summary_json)
    triggered = ctx.triggered_id

    if triggered == "xbar-r-dl-word":
        from pages.ai_download import _generate_word_download
        return _generate_word_download(summary, "Xbar-R")
    elif triggered == "xbar-r-dl-excel":
        from pages.ai_download import _generate_excel_download
        return _generate_excel_download(summary, "Xbar-R")
    return no_update
