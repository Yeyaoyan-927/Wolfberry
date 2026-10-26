"""规则模块快速单测：等级映射 / 多图汇总 / 订单状态机 / 差异标记。

用法：python scripts/test_rules.py   （不依赖 cv2 / 网络 / 数据库）
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.grading import (  # noqa: E402
    DIFF_BLUE, DIFF_GRAY, DIFF_GREEN, DIFF_RED, DIFF_YELLOW, diff_flag, map_grade,
)
from app.domain.order_state import can_transit  # noqa: E402
from app.domain.visual_summary import ImageCounts, summarize  # noqa: E402
from app.models.order import ST_CONFIRMING, ST_DONE, ST_SHIPPED, ST_TO_SHIP  # noqa: E402

ok_count = 0


def check(name: str, cond: bool, detail: str = ""):
    global ok_count
    mark = "PASS" if cond else "FAIL"
    if cond:
        ok_count += 1
    print(f"  [{mark}] {name}" + (f"  ({detail})" if detail and not cond else ""))


def test_grading():
    print("== 等级映射 ==")
    r = map_grade(defect_ratio=0.008, moldy_ratio=0.0, confidence=0.8)
    check("特优：缺陷率0.8%无霉变", r.grade == "特优", str(r.grade))

    r = map_grade(defect_ratio=0.018, moldy_ratio=0.001, confidence=0.8)
    check("特级：缺陷率1.8%", r.grade == "特级", str(r.grade))

    r = map_grade(defect_ratio=0.04, moldy_ratio=0.003, confidence=0.8)
    check("甲级：缺陷率4%", r.grade == "甲级", str(r.grade))

    r = map_grade(defect_ratio=0.08, moldy_ratio=0.004, confidence=0.8)
    check("乙级：缺陷率8%", r.grade == "乙级", str(r.grade))

    r = map_grade(defect_ratio=0.01, moldy_ratio=0.02, confidence=0.8)
    check("霉变一票否决→等外", r.grade == "等外", str(r.grade))

    r = map_grade(defect_ratio=0.005, moldy_ratio=0.0, confidence=0.30)
    check("置信0.30→灰(AI不参与)", r.grade is None and r.confidence_gray)


def test_summary():
    print("== 多图汇总 ==")
    imgs = [
        ImageCounts(image_id=1, grain_count=300, moldy=1, bad=4, oily=2, impurity=1, confidence=0.8),
        ImageCounts(image_id=2, grain_count=200, moldy=1, bad=3, oily=1, impurity=1, confidence=0.7),
        ImageCounts(image_id=3, grain_count=0, moldy=0, bad=0, oily=0, impurity=0,
                    confidence=0.5, valid=False, exclude_reason="未识别到果实"),
    ]
    s = summarize(imgs)
    # 合并计数：500 粒，缺陷 14 → 2.8%（铁律：不能对 2.67% 和 3% 取平均）
    check("总粒数=500", s.total_grains == 500)
    check("缺陷率=0.028（先合并计数再算比率）", abs(s.defect_ratio - 0.028) < 1e-9, str(s.defect_ratio))
    check("霉变率=0.004", abs(s.moldy_ratio - 0.004) < 1e-9)
    check("加权置信≈0.76", abs(s.weighted_confidence - (0.8*300 + 0.7*200)/500) < 1e-6)
    check("无效图剔除并提示", s.invalid_images == 1 and any("剔除" in w for w in s.warnings))

    # 批内差异告警
    imgs2 = [
        ImageCounts(image_id=1, grain_count=100, moldy=0, bad=1, oily=0, impurity=0, confidence=0.8),
        ImageCounts(image_id=2, grain_count=100, moldy=0, bad=20, oily=0, impurity=0, confidence=0.8),
    ]
    s2 = summarize(imgs2)
    check("极差>15%提示重新取样", any("重新取样" in w for w in s2.warnings))


def test_state():
    print("== 订单状态机 ==")
    check("待确认→待发货 合法", can_transit(ST_CONFIRMING, ST_TO_SHIP))
    check("待确认→已完成 非法", not can_transit(ST_CONFIRMING, ST_DONE))
    check("已发货→已完成 合法", can_transit(ST_SHIPPED, ST_DONE))
    check("已发货→已取消 非法（防绕过收货）", not can_transit(ST_SHIPPED, 5))


def test_diff_flag():
    print("== 差异标记 ==")
    check("一致→绿", diff_flag("特级", "特级", 0.8) == DIFF_GREEN)
    check("高报1级→黄", diff_flag("特优", "特级", 0.8) == DIFF_YELLOW)
    check("高报2级→红", diff_flag("特优", "乙级", 0.8) == DIFF_RED)
    check("低报→蓝", diff_flag("甲级", "特级", 0.8) == DIFF_BLUE)
    check("低置信→灰", diff_flag("特优", "甲级", 0.30) == DIFF_GRAY)
    check("无AI结果→灰", diff_flag("特级", None, None) == DIFF_GRAY)


if __name__ == "__main__":
    test_grading()
    test_summary()
    test_state()
    test_diff_flag()
    print(f"\n通过 {ok_count} 项")
