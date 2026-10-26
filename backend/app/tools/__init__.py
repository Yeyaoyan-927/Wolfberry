"""工具包入口：import 即完成注册。

新增 Skill 只需在此处 import 对应模块，无需改动调用方。
"""
from app.tools.base import ToolContext, ToolSpec, registry

# 注册内置工具（顺序无关）
from app.tools import price_suggest as _price_suggest  # noqa: E402,F401
from app.tools import product_optimize as _product_optimize  # noqa: E402,F401

__all__ = ["registry", "ToolSpec", "ToolContext"]
