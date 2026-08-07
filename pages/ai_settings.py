"""AI Settings placeholder page."""
import dash
from dash import html
import dash_bootstrap_components as dbc

dash.register_page(__name__, path="/ai-settings", name="AI Settings", title="AI Settings")

layout = dbc.Container([
    html.H3("🤖 AI Settings", className="mt-4"),
    dbc.Alert("AI 配置功能即将上线。目前请使用桌面版的 AI Settings 对话框。", color="info"),
    dbc.Card([
        dbc.CardHeader("配置说明"),
        dbc.CardBody([
            html.P("AI 增强解读支持以下后端："),
            html.Ul([
                html.Li("OpenAI (GPT-4o)"),
                html.Li("Ollama (本地部署，免费)"),
                html.Li("DeepSeek"),
                html.Li("Gemini / Kimi"),
            ]),
            html.P("配置文件位置: ~/.spc-tool/llm_config.json"),
        ]),
    ]),
], fluid=True)
