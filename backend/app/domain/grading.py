"""等级映射：缺陷率 → 外观等级（纯规则，无 IO，可单测）。

规则依据《枸杞交易平台-需求文档 v4.0》：
- 类别互斥优先级：霉变 > 坏果 > 油果 > 杂质 > 正常（汇总侧已保证一个果只计一类）
- 霉变率超过一票否决线 → 直接等外，不许上架
- AI 置信度 < 灰线 → AI 不参与等级判定（返回 None，由审核员人工定级）

阈值版本化：threshold_version 随结果一起落库，保证历史判定可复现。
"""
from __future__ import annotations

from dataclasses import dataclass, field


# ---------- 默认阈值（可被 settings 覆盖） ----------
DEFAULT_THRESHOLDS = {
    "moldy_veto": 0.015,   # 霉变率一票否决线
    "teyou_defect": 0.010, # 特优综合缺陷率上限
    "teyou_moldy": 0.0,    # 特优霉变率上限（不允许有霉变）
    "teji_defect": 0.020,  # 特级综合缺陷率上限
    "teji_moldy": 0.002,   # 特级霉变率上限
    "jia_defect": 0.050,   # 甲级综合缺陷率上限
    "jia_moldy": 0.005,    # 甲级霉变率上限
    "yi_defect": 0.100,    # 乙级综合缺陷率上限
}

GRADE_TEYOU = "特优"
GRADE_TEJI = "特级"
GRADE_JIA = "甲级"
GRADE_YI = "乙级"
GRADE_DENGWAI = "等外"


@dataclass
class GradeResult:
    """等级判定结果。

    grade 为 None 表示「灰」：置信不足，AI 不参与判定，交人工。
    reasons 记录每条触发的原因，供审核页与留痕展示。
    """

    grade: str | None
    confidence_gray: bool
    reasons: list[str] = field(default_factory=list)


def map_grade(
    *,
    defect_ratio: float,
    moldy_ratio: float,
    confidence: float,
    gray_conf: float = 0.45,
    thresholds: dict | None = None,
) -> GradeResult:
    """综合缺陷率 + 霉变率 + 置信度 → 等级。

    顺序固定：先灰线 → 再霉变一票否决 → 再逐级判定。
    """
    th = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    reasons: list[str] = []

    if confidence < gray_conf:
        return GradeResult(
            grade=None,
            confidence_gray=True,
            reasons=[f"置信度 {confidence:.2f} 低于灰线 {gray_conf:.2f}，AI 不参与判定"],
        )

    if moldy_ratio > th["moldy_veto"]:
        reasons.append(
            f"霉变率 {moldy_ratio:.2%} 超过一票否决线 {th['moldy_veto']:.2%}，判等外"
        )
        return GradeResult(grade=GRADE_DENGWAI, confidence_gray=False, reasons=reasons)

    if defect_ratio <= th["teyou_defect"] and moldy_ratio <= th["teyou_moldy"]:
        grade = GRADE_TEYOU
    elif defect_ratio <= th["teji_defect"] and moldy_ratio <= th["teji_moldy"]:
        grade = GRADE_TEJI
        reasons.append(f"综合缺陷率 {defect_ratio:.2%} 落在特级区间（≤{th['teji_defect']:.1%}）")
    elif defect_ratio <= th["jia_defect"] and moldy_ratio <= th["jia_moldy"]:
        grade = GRADE_JIA
        reasons.append(f"综合缺陷率 {defect_ratio:.2%} 落在甲级区间（≤{th['jia_defect']:.1%}）")
    elif defect_ratio <= th["yi_defect"]:
        grade = GRADE_YI
        reasons.append(f"综合缺陷率 {defect_ratio:.2%} 落在乙级区间（≤{th['yi_defect']:.1%}）")
    else:
        grade = GRADE_DENGWAI
        reasons.append(f"综合缺陷率 {defect_ratio:.2%} 超过乙级上限，判等外")

    return GradeResult(grade=grade, confidence_gray=False, reasons=reasons)


def rule_hits(*, defect_ratio: float, moldy_ratio: float, impurity_ratio: float,
              thresholds: dict | None = None) -> list[dict]:
    """阈值规则命中表（供审核工作台展示判定依据）。

    规则集与需求文档 v4.0 对齐；hit=True 表示违规命中。
    """
    th = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    return [
        {"code": "R1", "desc": f"霉变率 ≤ {th['moldy_veto']:.1%}",
         "hit": moldy_ratio > th["moldy_veto"],
         "value": f"{moldy_ratio:.2%}"},
        {"code": "R2", "desc": f"特优综合缺陷率 ≤ {th['teyou_defect']:.1%}",
         "hit": defect_ratio > th["teyou_defect"],
         "value": f"{defect_ratio:.2%}"},
        {"code": "R3", "desc": f"特级综合缺陷率 ≤ {th['teji_defect']:.1%}",
         "hit": defect_ratio > th["teji_defect"],
         "value": f"{defect_ratio:.2%}"},
        {"code": "R4", "desc": "综合缺陷率 ≤ 5%（甲/乙级线）",
         "hit": defect_ratio > th["jia_defect"],
         "value": f"{defect_ratio:.2%}"},
        {"code": "R6", "desc": "杂质率 ≤ 1%",
         "hit": impurity_ratio > 0.01,
         "value": f"{impurity_ratio:.2%}"},
    ]


# 差异标记：绿=一致 / 黄=高报1级 / 红=高报≥2级 / 蓝=低报 / 灰=AI不参与
DIFF_GREEN, DIFF_YELLOW, DIFF_RED, DIFF_BLUE, DIFF_GRAY = "绿", "黄", "红", "蓝", "灰"

_GRADE_ORDER = {GRADE_TEYOU: 4, GRADE_TEJI: 3, GRADE_JIA: 2, GRADE_YI: 1, GRADE_DENGWAI: 0}


def diff_flag(grade_claim: str | None, ai_grade: str | None, confidence: float | None,
              gray_conf: float = 0.45) -> str:
    """卖家自述等级 vs AI 建议等级 → 五色差异标记。

    AI 无结果或置信低于灰线 → 灰（AI 不参与判定，纯人工）。
    """
    if not grade_claim or not ai_grade or confidence is None or confidence < gray_conf:
        return DIFF_GRAY
    if grade_claim not in _GRADE_ORDER or ai_grade not in _GRADE_ORDER:
        return DIFF_GRAY
    gap = _GRADE_ORDER[grade_claim] - _GRADE_ORDER[ai_grade]
    if gap >= 2:
        return DIFF_RED      # 高报 ≥2 级
    if gap == 1:
        return DIFF_YELLOW   # 高报 1 级
    if gap < 0:
        return DIFF_BLUE     # 低报（AI 认为更好）
    return DIFF_GREEN
