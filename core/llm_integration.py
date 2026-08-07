"""
LLM Integration Module - AI-enhanced expert analysis for SPC Tool.

Supports multiple LLM backends (OpenAI-compatible API):
- OpenAI (GPT-4o, GPT-4)
- Ollama (local, offline)
- Azure OpenAI
- Gemini, Kimi, DeepSeek
- Custom API endpoint

Provides:
- Enhanced interpretation of control chart results
- Root cause suggestions for out-of-control conditions
- Process improvement action plans
- Interactive Q&A about SPC analysis
"""

import json
import os
from typing import Optional
from dataclasses import dataclass
from pathlib import Path


@dataclass
class LLMConfig:
    """Configuration for LLM backend."""
    enabled: bool = False
    backend: str = "openai"  # "openai", "ollama", "azure", "gemini", "kimi", "custom"
    model: str = "gpt-4o"
    api_key: str = ""
    base_url: str = ""
    temperature: float = 0.3
    max_tokens: int = 2000
    language: str = "zh"

    # Azure-specific
    azure_endpoint: str = ""
    azure_deployment: str = ""
    azure_api_version: str = "2024-02-01"


CONFIG_PATH = Path.home() / ".spc-tool" / "llm_config.json"


def load_config() -> LLMConfig:
    """Load LLM config from file."""
    config = LLMConfig()
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                for k, v in data.items():
                    if hasattr(config, k):
                        setattr(config, k, v)
        except (json.JSONDecodeError, IOError):
            pass
    return config


def save_config(config: LLMConfig):
    """Save LLM config to file."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "enabled": config.enabled,
        "backend": config.backend,
        "model": config.model,
        "api_key": config.api_key,
        "base_url": config.base_url,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "language": config.language,
        "azure_endpoint": config.azure_endpoint,
        "azure_deployment": config.azure_deployment,
        "azure_api_version": config.azure_api_version,
    }
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _get_client(config: LLMConfig):
    """Create OpenAI-compatible client based on config."""
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError(
            "openai package required for AI features. "
            "Install with: pip install openai"
        )

    if config.backend == "openai":
        return OpenAI(api_key=config.api_key)
    elif config.backend == "ollama":
        base_url = config.base_url or "http://localhost:11434/v1"
        return OpenAI(base_url=base_url, api_key="ollama")
    elif config.backend == "azure":
        from openai import AzureOpenAI
        return AzureOpenAI(
            azure_endpoint=config.azure_endpoint,
            api_key=config.api_key,
            api_version=config.azure_api_version,
        )
    elif config.backend == "gemini":
        base_url = config.base_url or "https://generativelanguage.googleapis.com/v1beta/openai/"
        return OpenAI(base_url=base_url, api_key=config.api_key)
    elif config.backend == "kimi":
        base_url = config.base_url or "https://api.moonshot.cn/v1"
        return OpenAI(base_url=base_url, api_key=config.api_key)
    elif config.backend == "custom":
        return OpenAI(base_url=config.base_url, api_key=config.api_key or "none")
    else:
        raise ValueError(f"Unknown backend: {config.backend}")


def _build_system_prompt(config: LLMConfig) -> str:
    """Build system prompt for SPC expert role."""
    if config.language == "zh":
        return """你是一位经验丰富的六西格玛黑带大师和统计过程控制（SPC）专家。
你精通 AIAG SPC 参考手册（2026版）的所有内容，包括计量型和计数型控制图、过程能力分析、
判异规则（Western Electric Rules）、过程改进方法论。

你的职责是：
1. 基于控制图和能力分析结果，给出深入的专业解读
2. 准确识别过程失控的根因——区分特殊原因变异和普通原因变异
3. 对判异规则触发的模式给出具体的物理解释（如刀具磨损、材料批次差异、操作班次变化等）
4. 给出具体、可操作的过程改进建议，按优先级排序
5. 评估过程能力不足对产品质量的风险影响

回答时请：
- 使用结构化格式（标题、编号、要点）
- 引用具体数值支持你的判断
- 区分"特殊原因"和"普通原因"，并给出对应的处理策略
- 提供 AIAG SPC 标准的参考依据
- 区分控制限（过程的声音）和规格限（客户的声音）的概念

【重要】你必须使用中文回答。"""
    else:
        return """You are a seasoned Six Sigma Black Belt Master and Statistical Process Control (SPC) expert.
You are thoroughly versed in the AIAG SPC Reference Manual (2026 Edition), covering variables and
attributes control charts, process capability analysis, out-of-control rules (Western Electric Rules),
and process improvement methodology.

Your responsibilities:
1. Provide deep professional interpretation based on control chart and capability results
2. Accurately identify root causes of out-of-control conditions — distinguishing special causes from common causes
3. Give specific physical explanations for triggered rule patterns (e.g., tool wear, material batch variation, shift changes)
4. Provide specific, actionable process improvement recommendations prioritized by urgency
5. Assess risk impact of inadequate process capability on product quality

When responding:
- Use structured format (headings, numbered points)
- Cite specific numerical values to support judgments
- Distinguish "special causes" from "common causes" with corresponding handling strategies
- Reference AIAG SPC standard guidelines
- Distinguish control limits (voice of the process) from spec limits (voice of the customer)

IMPORTANT: Respond in English only."""


def enhance_interpretation(
    analysis_summary: dict,
    config: Optional[LLMConfig] = None,
) -> str:
    """
    Enhance SPC analysis interpretation with LLM.

    Parameters
    ----------
    analysis_summary : dict
        Summary of analysis results including:
        - chart_type: str (e.g., "Xbar-R", "P", "Capability")
        - in_control: bool
        - violations: dict (test_num -> indices)
        - limits: dict (UCL, CL, LCL)
        - capability: dict (Cp, Cpk, etc.) if applicable
        - sigma_within, sigma_overall: float
        - data_summary: str (descriptive stats)
    config : LLMConfig, optional

    Returns
    -------
    str
        Enhanced interpretation (markdown formatted)
    """
    if config is None:
        config = load_config()

    if not config.enabled:
        return ""

    from src.i18n.translations import get_language
    config.language = get_language()

    client = _get_client(config)
    context = _format_spc_context(analysis_summary, config.language)

    if config.language == "zh":
        user_prompt = f"""以下是一份 SPC 分析的结果。请给出你的专业解读和改进建议。

{context}

请提供：
1. 对控制图状态的深入解读（不仅是受控/失控的判定，而是模式背后的含义）
2. 如果有判异规则触发：可能的物理原因和对应的排查方向
3. 如果有能力分析：对过程能力水平的评价和改进方向
4. 具体的过程改进建议（短期/中期/长期）
5. 对后续监控的建议"""
    else:
        user_prompt = f"""Below are the results of an SPC analysis. Please provide your professional interpretation.

{context}

Please provide:
1. Deep interpretation of control chart status (not just in/out of control, but the meaning behind patterns)
2. If rules are triggered: possible physical causes and investigation directions
3. If capability analysis present: evaluation of capability level and improvement direction
4. Specific process improvement recommendations (short/medium/long term)
5. Recommendations for ongoing monitoring"""

    try:
        model = config.azure_deployment if config.backend == "azure" else config.model
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _build_system_prompt(config)},
                {"role": "user", "content": user_prompt},
            ],
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"[LLM Error: {type(e).__name__}: {e}]"


def ask_question(
    question: str,
    analysis_summary: dict,
    config: Optional[LLMConfig] = None,
) -> str:
    """
    Answer a user question about SPC analysis results.

    Parameters
    ----------
    question : str
        User's question
    analysis_summary : dict
        Current analysis state
    config : LLMConfig, optional

    Returns
    -------
    str
    """
    if config is None:
        config = load_config()

    if not config.enabled:
        return "AI 功能未启用。请在设置中配置 LLM 后端。" if config.language == "zh" else "AI not enabled."

    from src.i18n.translations import get_language
    config.language = get_language()

    client = _get_client(config)
    context = _format_spc_context(analysis_summary, config.language)

    user_prompt = f"""SPC 分析背景：
{context}

用户问题：{question}

请基于以上 SPC 分析数据，专业地回答用户的问题。"""

    try:
        model = config.azure_deployment if config.backend == "azure" else config.model
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _build_system_prompt(config)},
                {"role": "user", "content": user_prompt},
            ],
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"[LLM Error: {type(e).__name__}: {e}]"


def _format_spc_context(analysis_summary: dict, lang: str) -> str:
    """Format SPC analysis data into context string for LLM."""
    parts = []

    chart_type = analysis_summary.get("chart_type", "Unknown")
    parts.append(f"{'控制图类型' if lang == 'zh' else 'Chart Type'}: {chart_type}")

    in_control = analysis_summary.get("in_control")
    if in_control is not None:
        status = ("受控" if in_control else "失控") if lang == "zh" else ("In Control" if in_control else "Out of Control")
        parts.append(f"{'过程状态' if lang == 'zh' else 'Status'}: {status}")

    # Control limits
    limits = analysis_summary.get("limits", {})
    if limits:
        parts.append(f"\n{'控制限' if lang == 'zh' else 'Control Limits'}:")
        for k, v in limits.items():
            parts.append(f"  {k}: {v}")

    # Violations
    violations = analysis_summary.get("violations", {})
    if violations:
        parts.append(f"\n{'判异规则触发' if lang == 'zh' else 'Rules Triggered'}:")
        for test_num, indices in violations.items():
            parts.append(f"  Test {test_num}: {'子组' if lang == 'zh' else 'subgroups'} {indices[:10]}")

    # Sigma
    sw = analysis_summary.get("sigma_within")
    so = analysis_summary.get("sigma_overall")
    if sw is not None:
        parts.append(f"\nσ_within = {sw:.6f}")
    if so is not None:
        parts.append(f"σ_overall = {so:.6f}")

    # Capability
    capability = analysis_summary.get("capability", {})
    if capability:
        parts.append(f"\n{'过程能力' if lang == 'zh' else 'Process Capability'}:")
        for k, v in capability.items():
            parts.append(f"  {k} = {v}")

    # Data summary
    data_summary = analysis_summary.get("data_summary", "")
    if data_summary:
        parts.append(f"\n{'数据概要' if lang == 'zh' else 'Data Summary'}: {data_summary}")

    return "\n".join(parts)


def test_connection(config: Optional[LLMConfig] = None) -> tuple:
    """
    Test LLM connection.

    Returns
    -------
    tuple of (bool, str)
    """
    if config is None:
        config = load_config()

    if not config.enabled:
        return False, "LLM is disabled."

    try:
        client = _get_client(config)
        model = config.azure_deployment if config.backend == "azure" else config.model
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Say OK"}],
            max_tokens=10,
        )
        return True, f"Connected. Model: {model}"
    except ImportError as e:
        return False, f"Missing package: {e}. Install with: pip install openai"
    except Exception as e:
        error_msg = str(e)
        if "404" in error_msg:
            return False, f"Model '{config.model}' not found."
        return False, f"Failed: {type(e).__name__}: {e}"
