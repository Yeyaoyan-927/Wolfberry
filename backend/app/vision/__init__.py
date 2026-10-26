"""视觉检测：图片 → 计数与缺陷分类。"""
from app.vision.detector import DetectResult, detect_opencv, get_detector

__all__ = ["DetectResult", "detect_opencv", "get_detector"]
