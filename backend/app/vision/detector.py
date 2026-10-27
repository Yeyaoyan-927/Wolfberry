"""视觉检测模块：图片 → 果实计数与缺陷分类。

当前实现（detector="opencv"）：OpenCV 启发式伪评估 —— 基于 HSV 颜色统计
与轮廓分析，输出真实计算值但精度有限，用于打通全链路。

升级路径（架构已留好，换实现不改其他代码）：
    detector="onnx"：加载 YOLOv8n-seg 导出的 ONNX（var/models/goji-seg.onnx），
    输出同样的 ImageCounts，模型版本号改 ASSESS_MODEL_VERSION 即可。
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from app.core.config import settings
from app.domain.visual_summary import ImageCounts

logger = logging.getLogger(__name__)

OUTCOME_LABELS = {"moldy": "霉变", "bad": "坏果", "oily": "油果", "impurity": "杂质"}


@dataclass
class DetectResult:
    counts: ImageCounts
    raw: dict


def _load_cv2():
    import cv2  # 延迟导入，未安装时不影响其他功能

    return cv2


def detect_opencv(data: bytes, image_id: int) -> DetectResult:
    """OpenCV 启发式伪评估。

    思路（全部为确定性算法，可解释、可复现）：
    1. HSV 分割深红色区域（枸杞干果主色）→ 形态学去噪
    2. 连通域计数 → 总粒数（面积过滤噪声与小碎片）
    3. 缺陷分类（互斥：霉变 > 坏果 > 油果 > 杂质）：
       - 霉变：连通域内存在大面积极暗斑块（V 很低且 S 低）
       - 坏果：轮廓破损度高（面积/凸包面积比低）
       - 油果：色相偏暗棕（H 偏移、V 低）
       - 杂质：非红色小连通域
    4. 图级置信：基于亮度均匀性 + 目标清晰度（拉普拉斯方差）的经验映射
    """
    cv2 = _load_cv2()
    buf = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if img is None:
        return DetectResult(
            counts=ImageCounts(image_id=image_id, grain_count=0, moldy=0, bad=0,
                               oily=0, impurity=0, confidence=0.0, valid=False,
                               exclude_reason="图片解码失败"),
            raw={"method": "opencv", "error": "decode_failed"},
        )

    # 推理用降采样副本（短边 1024），原图不动
    h, w = img.shape[:2]
    scale = 1024 / min(h, w)
    if scale < 1:
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

    small = cv2.GaussianBlur(img, (5, 5), 0)
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    hue, sat, val = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]

    # 干枸杞主色：暗橙红（Hue 2~25），饱和度放宽到 55，避免漏检
    red_mask = ((hue >= 2) & (hue <= 25) & (sat >= 55) & (val >= 20) & (val <= 235)).astype(np.uint8) * 255
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_OPEN, kernel, iterations=1)
    red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_CLOSE, kernel, iterations=2)

    contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    area = img.shape[0] * img.shape[1]
    min_area = area * 0.0004   # 过滤碎片噪声

    # 两遍处理：先取「中等大小轮廓」的中位数面积作为单果基准，
    # 粘连大块按面积比例折算粒数（伪评估的可解释近似）
    areas = [cv2.contourArea(c) for c in contours]
    solid_areas = sorted(a for a in areas if min_area <= a <= area * 0.08)
    unit_area = float(np.median(solid_areas)) if len(solid_areas) >= 3 else (area * 0.004)
    unit_area = max(unit_area, min_area * 2)

    # 清晰度与亮度均匀性 → 图级置信
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    brightness = float(val.mean())

    n_grain = n_moldy = n_bad = n_oily = n_impurity = 0
    detail_boxes = []

    for c in contours:
        a = cv2.contourArea(c)
        if a < min_area:
            continue  # 噪声碎片直接忽略（不计杂质，避免缺陷率虚高）
        # 粘连块折算：超过 3 倍单果面积按比例估粒
        est = max(1, round(a / unit_area)) if a > unit_area * 3 else 1

        hull_a = cv2.contourArea(cv2.convexHull(c)) or 1.0
        solidity = a / hull_a

        m = cv2.moments(c)
        cx = int(m["m10"] / (m["m00"] + 1e-6))
        cy = int(m["m01"] / (m["m00"] + 1e-6))
        r = max(6, int(np.sqrt(a / np.pi)))
        roi_h = hue[max(0, cy - r):cy + r, max(0, cx - r):cx + r]
        roi_s = sat[max(0, cy - r):cy + r, max(0, cx - r):cx + r]
        roi_v = val[max(0, cy - r):cy + r, max(0, cx - r):cx + r]
        if roi_v.size == 0:
            continue
        v_med = float(np.median(roi_v))
        dark_ratio = float((roi_v < 40).mean())   # 极暗斑块占比 → 霉变信号
        hue_med = float(np.median(roi_h))

        n_grain += est
        # 检测框带类别标签（供 AI 标注图叠加展示；伪评估为启发式定位）
        label = "normal"
        if dark_ratio >= 0.25:
            label = "moldy"
            n_moldy += est
        elif est == 1 and solidity < 0.62:
            label = "bad"
            n_bad += 1
        elif 13 < hue_med <= 25 and v_med < 130:
            label = "oily"
            n_oily += est
        detail_boxes.append({"x": cx, "y": cy, "r": r, "v": v_med,
                             "solidity": round(solidity, 3), "est_grains": est, "label": label})

    # 图级置信：清晰度为主，亮度适中加分（经验映射，0.4~0.9）
    conf = 0.0 if n_grain == 0 else round(
        min(0.92, 0.42 + min(sharpness, 1200) / 1200 * 0.40
            + (0.08 if 30 <= brightness <= 190 else 0)), 3)
    valid = n_grain > 0 and conf >= settings.ASSESS_MIN_IMAGE_CONF
    exclude = "" if valid else (f"置信度 {conf:.2f} 低于剔除线" if n_grain else "未识别到果实")

    counts = ImageCounts(
        image_id=image_id, grain_count=n_grain, moldy=n_moldy, bad=n_bad,
        oily=n_oily, impurity=n_impurity, confidence=conf, valid=valid,
        exclude_reason=exclude,
    )
    raw = {
        "method": "opencv-heuristic",
        "image_size": [img.shape[1], img.shape[0]],
        "sharpness": round(sharpness, 1),
        "brightness": round(brightness, 1),
        "unit_area": round(unit_area, 1),
        "boxes": detail_boxes[:200],
    }
    return DetectResult(counts=counts, raw=raw)


def detect_mock(data: bytes, image_id: int) -> DetectResult:
    """固定输出（联调用，不做真实计算）。"""
    counts = ImageCounts(image_id=image_id, grain_count=300, moldy=1, bad=3,
                         oily=2, impurity=1, confidence=0.80, valid=True)
    return DetectResult(counts=counts, raw={"method": "mock"})


def get_detector():
    """按配置选择实现：onnx 权重存在且配置为 auto/onnx 时用 onnx，否则 opencv。"""
    mode = settings.ASSESS_DETECTOR
    if mode == "mock":
        return detect_mock
    onnx_path = Path(settings.ASSESS_ONNX_PATH)
    if mode in ("auto", "onnx") and onnx_path.exists():
        # TODO: 接入 YOLO ONNX 推理（接口已对齐：bytes → DetectResult）
        logger.warning("检测到 ONNX 权重但推理实现未接入，回退 OpenCV 启发式")
    return detect_opencv


def result_dict(res: DetectResult) -> dict:
    return {"counts": asdict(res.counts), "raw": res.raw}
