"""商品优化建议规则（纯函数）。

输入商品与图片的客观数据，输出按严重程度排序的改进项。
只给建议，不承诺改了就一定过审。
"""
from __future__ import annotations

from dataclasses import dataclass, field

GRADE_ORDER = ("特优", "特级", "甲级", "乙级", "等外")

# 阈值集中在此，便于后续迁移到配置表
MOLDY_HIGH = 0.005
DEFECT_HIGH = 0.05
DEFECT_MEDIUM = 0.03
CONF_LOW = 0.45
OCCLUSION_MAX = 0.30
MIN_IMAGES = 3
DESC_MIN_LEN = 20

_SEVERITY_WEIGHT = {"high": 3, "medium": 2, "low": 1}


@dataclass
class Issue:
    code: str
    severity: str
    title: str
    detail: str
    action: str
    expected_effect: str


@dataclass
class OptimizeAdvice:
    risk_level: str
    summary: str
    issues: list[Issue] = field(default_factory=list)


def grade_gap(claim: str, ai: str | None) -> int | None:
    """返回高报级数：正数=自述高于 AI 建议，负数=低报。"""
    if not ai or claim not in GRADE_ORDER or ai not in GRADE_ORDER:
        return None
    return GRADE_ORDER.index(ai) - GRADE_ORDER.index(claim)


def build_advice(
    *,
    image_count: int,
    invalid_images: list[dict],
    max_occlusion: float,
    grade_claim: str,
    ai_grade: str | None,
    ai_confidence: float | None,
    defect_ratio: float | None,
    moldy_ratio: float | None,
    description_len: int,
) -> OptimizeAdvice:
    issues: list[Issue] = []

    if image_count < MIN_IMAGES:
        issues.append(
            Issue(
                code="IMAGE_COUNT",
                severity="high",
                title="实拍图数量不足",
                detail=f"当前 {image_count} 张，平台要求至少 {MIN_IMAGES} 张。",
                action="补拍 1~2 张：一张全貌俯拍，一张局部细节。",
                expected_effect="满足提交前置校验，减少因材料不全被直接退回。",
            )
        )

    if invalid_images:
        reasons = "；".join(
            f"{item.get('file_name', '图片')}：{item.get('reason', '未通过校验')}"
            for item in invalid_images[:3]
        )
        issues.append(
            Issue(
                code="IMAGE_QUALITY",
                severity="high",
                title="存在未通过校验的图片",
                detail=reasons,
                action="按提示重拍：平铺单层、白底、室内均匀光、正上方俯拍、关闭闪光灯。",
                expected_effect="提升识别置信度，避免评估被判定为无效图。",
            )
        )

    if max_occlusion > OCCLUSION_MAX:
        issues.append(
            Issue(
                code="OCCLUSION",
                severity="medium",
                title="果实重叠率偏高",
                detail=f"最高遮挡率 {max_occlusion:.0%}，超过 {OCCLUSION_MAX:.0%} 上限。",
                action="把样品摊开成单层后重拍，避免堆叠。",
                expected_effect="遮挡会漏计粒数、低估缺陷率，摊开后数据更接近真实。",
            )
        )

    gap = grade_gap(grade_claim, ai_grade)
    if gap is not None and gap >= 2:
        issues.append(
            Issue(
                code="GRADE_OVERCLAIM",
                severity="high",
                title=f"自述等级明显偏高（高报 {gap} 级）",
                detail=f"自述「{grade_claim}」，图像评估建议「{ai_grade}」。",
                action=f"把等级调整为「{ai_grade}」，或补充更清晰的细节图后重新提交。",
                expected_effect="红标商品默认按驳回处理，改级后通过率明显提升。",
            )
        )
    elif gap is not None and gap == 1:
        issues.append(
            Issue(
                code="GRADE_SLIGHT_OVERCLAIM",
                severity="medium",
                title="自述等级偏高 1 级",
                detail=f"自述「{grade_claim}」，图像评估建议「{ai_grade}」。",
                action="核对缺陷率后决定：改级可快速通过，保留原级需准备更充分的图。",
                expected_effect="黄标商品会进入重点审核，审核时长通常延长。",
            )
        )

    if moldy_ratio is not None and moldy_ratio > MOLDY_HIGH:
        issues.append(
            Issue(
                code="MOLDY",
                severity="high",
                title="霉变率超出容忍线",
                detail=f"检测到霉变率 {moldy_ratio:.2%}，平台一票否决线为 {MOLDY_HIGH:.1%}。",
                action="人工挑拣霉变果后重新取样拍照；若比例确实偏高，建议按「等外」处理。",
                expected_effect="霉变是硬性指标，挑拣后重拍才有可能进入正常等级。",
            )
        )

    if defect_ratio is not None and defect_ratio > DEFECT_HIGH:
        issues.append(
            Issue(
                code="DEFECT_HIGH",
                severity="medium",
                title="综合缺陷率偏高",
                detail=f"当前 {defect_ratio:.2%}，超过 {DEFECT_HIGH:.1%}。",
                action="挑拣坏果、油果、杂质后重新取样。",
                expected_effect="缺陷率每下降 1 个百分点，等级与议价空间都会改善。",
            )
        )
    elif defect_ratio is not None and defect_ratio > DEFECT_MEDIUM:
        issues.append(
            Issue(
                code="DEFECT_MEDIUM",
                severity="low",
                title="缺陷率处于临界区间",
                detail=f"当前 {defect_ratio:.2%}，接近 {DEFECT_HIGH:.1%} 的分界。",
                action="如追求更高等级，可做一次精选后重拍。",
                expected_effect="小幅优化即可跨过等级分界。",
            )
        )

    if ai_confidence is not None and ai_confidence < CONF_LOW:
        issues.append(
            Issue(
                code="LOW_CONFIDENCE",
                severity="medium",
                title="图像评估置信度偏低",
                detail=f"当前置信度 {ai_confidence:.2f}，低于 {CONF_LOW}。",
                action="补拍 1~2 张清晰细节图，避免逆光与阴影。",
                expected_effect="置信度提升后，评估建议才会计入等级差异判定。",
            )
        )

    if description_len < DESC_MIN_LEN:
        issues.append(
            Issue(
                code="DESC_SHORT",
                severity="low",
                title="商品描述过于简单",
                detail=f"当前 {description_len} 字，建议不少于 {DESC_MIN_LEN} 字。",
                action="补充采摘年份、晾晒方式、含水率、包装与发货时效。",
                expected_effect="减少买家反复问询，也降低审核员要求补充材料的概率。",
            )
        )

    issues.sort(key=lambda i: _SEVERITY_WEIGHT.get(i.severity, 0), reverse=True)

    if any(i.severity == "high" for i in issues):
        risk = "high"
        summary = "存在会导致驳回的硬性问题，建议先处理高优先级项再提交。"
    elif any(i.severity == "medium" for i in issues):
        risk = "medium"
        summary = "没有硬性拦截项，但有几处会拖慢审核或压低成交价。"
    elif issues:
        risk = "low"
        summary = "整体质量不错，只有少量可优化项。"
    else:
        risk = "low"
        summary = "未发现明显问题，可以提交审核。"

    return OptimizeAdvice(risk_level=risk, summary=summary, issues=issues)
