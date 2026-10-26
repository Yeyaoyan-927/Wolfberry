"""多图汇总：逐图计数 → 样品级指标（纯函数）。

铁律（需求文档 v4.0 架构底线第 6 条）：
- 先合并各类计数，再算比率；禁止对各图比率取算术平均
- 图级置信低于剔除线、或粒数为 0 的图视为无效，不参与汇总但记录在案
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ImageCounts:
    """单张图的检测结果（由 detector 输出）。"""

    image_id: int
    grain_count: int          # 识别到的总粒数
    moldy: int                # 霉变
    bad: int                  # 坏果（破碎/干瘪）
    oily: int                 # 油果
    impurity: int             # 杂质
    confidence: float         # 图级置信 0~1
    valid: bool = True        # 是否参与汇总
    exclude_reason: str = ""


@dataclass
class SampleSummary:
    """样品级汇总结果。"""

    total_grains: int = 0
    moldy: int = 0
    bad: int = 0
    oily: int = 0
    impurity: int = 0
    defect_ratio: float = 0.0     # (霉变+坏果+油果+杂质) / 总粒数
    moldy_ratio: float = 0.0
    weighted_confidence: float = 0.0   # 按粒数加权
    valid_images: int = 0
    invalid_images: int = 0
    warnings: list[str] = field(default_factory=list)


def summarize(images: list[ImageCounts], min_grains: int = 20) -> SampleSummary:
    """合并计数 → 计算比率 → 有效性提示。

    剔除规则：
    - confidence < 有效线（调用方在 detector 侧已标注 valid=False）
    - grain_count <= 0（没识别到果，可能是误传图）
    - 汇总后总粒数 < min_grains → 代表性不足，仅提示不拦截（审核员判断）
    """
    out = SampleSummary()
    usable = [im for im in images if im.valid and im.grain_count > 0]
    out.invalid_images = len(images) - len(usable)
    for im in images:
        if im not in usable:
            out.warnings.append(f"图片 #{im.image_id} 剔除：{im.exclude_reason or '未识别到果实'}")
    if not usable:
        out.warnings.append("无有效图片，无法汇总")
        return out

    out.valid_images = len(usable)
    out.total_grains = sum(im.grain_count for im in usable)
    out.moldy = sum(im.moldy for im in usable)
    out.bad = sum(im.bad for im in usable)
    out.oily = sum(im.oily for im in usable)
    out.impurity = sum(im.impurity for im in usable)

    total = out.total_grains
    defect = out.moldy + out.bad + out.oily + out.impurity
    # 铁律：先合并计数，再算比率
    out.defect_ratio = round(defect / total, 4)
    out.moldy_ratio = round(out.moldy / total, 4)
    # 按粒数加权平均置信度
    out.weighted_confidence = round(
        sum(im.confidence * im.grain_count for im in usable) / total, 3
    )

    if total < min_grains:
        out.warnings.append(f"总粒数 {total} 少于 {min_grains}，代表性不足，建议补充图片")

    # 批内一致性：单图缺陷率极差过大提示重新取样
    ratios = []
    for im in usable:
        d = im.moldy + im.bad + im.oily + im.impurity
        ratios.append(d / im.grain_count)
    if len(ratios) >= 2 and (max(ratios) - min(ratios)) > 0.15:
        out.warnings.append("各图缺陷率差异较大（极差>15%），批内不均匀，建议重新取样")

    return out
