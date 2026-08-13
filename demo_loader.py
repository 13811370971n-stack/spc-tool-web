"""
Demo data loader for SPC Tool Web.
Provides pre-configured data + column selections for each chart type.
"""

import os
import pandas as pd
import json

DEMO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_data")

# Demo configurations: which file, which columns, which parameters
DEMO_CONFIG = {
    "xbar-r": {
        "file": "SPC_钢珠直径.XLS",
        "description": "钢珠直径 - 25子组×5样品",
        "data_cols": ["直径1", "直径2", "直径3", "直径4", "直径5"],
        "subgroup_col": None,
        "usl": None,
        "lsl": None,
        "tests": [1, 2, 3, 4],
    },
    "xbar-s": {
        "file": "SPC_芯片镀膜.XLS",
        "description": "芯片镀膜厚度 - 25子组×5样品",
        "data_cols": ["1", "2", "3", "4", "5"],
        "tests": [1, 2, 3, 4],
    },
    "imr": {
        "file": "SPC_尾气浓度.XLS",
        "description": "尾气浓度 - 75个观测值",
        "data_col": "尾气浓度",
        "usl": None,
        "lsl": None,
        "tests": [1, 2, 3, 4],
    },
    "p-chart": {
        "file": "SPC_二极管不合格品率.XLS",
        "description": "二极管不合格品率 - 30子组, n=150",
        "defect_col": "不合格品数量",
        "size_col": "样品数量",
        "tests": [1, 2, 3, 4],
    },
    "np-chart": {
        "file": "SPC_二极管不合格品率.XLS",
        "description": "二极管不合格品数 - n=150",
        "defect_col": "不合格品数量",
        "sample_size": 150,
        "tests": [1, 2, 3, 4],
    },
    "c-chart": {
        "file": "SPC_芯片缺陷率.XLS",
        "description": "芯片缺陷数 - 15子组",
        "defect_col": "缺陷数",
        "tests": [1, 2, 3, 4],
    },
    "u-chart": {
        "file": "SPC_芯片缺陷率.XLS",
        "description": "芯片单位缺陷率 - 15子组",
        "defect_col": "缺陷数",
        "size_col": "样品数量",
        "tests": [1, 2, 3, 4],
    },
    "ewma": {
        "file": "SPC_EWMA控制图.XLS",
        "description": "镀膜厚度 EWMA - 20观测, λ=0.2",
        "data_col": "厚度",
        "lambda": 0.2,
        "L": 3.0,
    },
    "zmr": {
        "file": "SPC_ZMR控制图.XLS",
        "description": "短期生产重量 - 3种零件类型",
        "data_col": "重量",
        "type_col": "类型",
    },
    "capability": {
        "file": "SPC_BoxCox变换.XLS",
        "description": "杂质含量 - Box-Cox变换能力分析",
        "data_col": "杂质含量",
        "usl": 20,
        "lsl": 0,
        "transform": "boxcox",
    },
    "normality": {
        "file": "SPC_尾气浓度.XLS",
        "description": "尾气浓度正态性检验",
        "data_col": "尾气浓度",
        "alpha": 0.05,
    },
}


def load_demo_data(chart_type: str) -> tuple:
    """
    Load demo data for a given chart type.
    
    Returns:
        (df_json, config) where df_json is JSON-serialized DataFrame
        and config is the demo parameters dict.
    """
    if chart_type not in DEMO_CONFIG:
        return None, None
    
    config = DEMO_CONFIG[chart_type]
    filepath = os.path.join(DEMO_DIR, config["file"])
    
    if not os.path.exists(filepath):
        return None, None
    
    df = pd.read_excel(filepath, engine="xlrd")
    df_json = df.to_json(date_format="iso", orient="split")
    
    return df_json, config


def get_demo_description(chart_type: str) -> str:
    """Get demo data description for a chart type."""
    if chart_type in DEMO_CONFIG:
        return DEMO_CONFIG[chart_type]["description"]
    return ""
