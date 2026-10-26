"""应用配置：分层加载 + 环境隔离。

优先级（后者覆盖前者）：
    .env  ->  .env.<APP_ENV>  ->  进程环境变量

密钥只从环境变量读取，仓库内不出现任何明文凭据。
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]  # backend/


def _current_env() -> str:
    return os.getenv("APP_ENV", "dev").strip() or "dev"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BASE_DIR / ".env", BASE_DIR / f".env.{_current_env()}"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---------- 应用 ----------
    APP_ENV: str = "dev"
    APP_NAME: str = "wolfberry"
    API_PREFIX: str = "/api/v1"
    DEBUG: bool = True

    # ---------- 数据库 ----------
    DATABASE_URL: str = "mysql+pymysql://root:yeyaoyan@127.0.0.1:3306/wolfberry?charset=utf8mb4"
    DB_ECHO: bool = False

    # ---------- 鉴权 ----------
    JWT_SECRET: str = "dev-only-please-override"
    JWT_ALG: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 240

    # ---------- 对象存储 ----------
    # auto: 有 COS 凭据走 COS，否则本地；也可强制 cos / local
    STORAGE_DRIVER: str = "auto"
    STORAGE_LOCAL_DIR: str = str(BASE_DIR / "var" / "uploads")
    STORAGE_PUBLIC_BASE: str = ""  # 本地存储对外前缀，空则用请求 host

    COS_SECRET_ID: str = ""
    COS_SECRET_KEY: str = ""
    COS_BUCKET: str = "wolfberry-1361042049"
    COS_REGION: str = "ap-shanghai"
    COS_DOMAIN: str = "wolfberry-1361042049.cos.ap-shanghai.myqcloud.com"
    COS_SCHEME: str = "https"
    COS_SIGNED_URL_TTL: int = 3600
    COS_PUBLIC_READ: bool = False  # 桶为公有读时直接拼接域名，否则签发临时 URL

    # ---------- 大模型 ----------
    DASHSCOPE_API_KEY: str = ""
    DASHSCOPE_BASE_URL: str = "https://dashscope.aliyuncs.com/api/v1"
    LLM_MODEL: str = "qwen-plus"
    LLM_TIMEOUT: int = 30
    LLM_MAX_TOKENS: int = 1200

    # ---------- 向量 ----------
    EMBEDDING_PROVIDER: str = "auto"  # auto | dashscope | local
    EMBEDDING_MODEL: str = "text-embedding-v3"
    EMBEDDING_DIM: int = 1024  # dashscope 输出维度；本地哈希向量固定 512
    EMBEDDING_BATCH: int = 10  # DashScope text-embedding 单批上限 10 条

    # ---------- RAG ----------
    RAG_TOP_K: int = 5
    RAG_CHUNK_SIZE: int = 500
    RAG_CHUNK_OVERLAP: int = 80
    RAG_MIN_SCORE: float = 0.18
    RAG_MAX_DOC_MB: int = 20

    # ---------- 图像评估 ----------
    ASSESS_ENABLED: bool = True
    # auto: 有 ONNX 权重用模型，否则 OpenCV 启发式；可强制 mock / opencv / onnx
    ASSESS_DETECTOR: str = "auto"
    ASSESS_ONNX_PATH: str = str(BASE_DIR / "var" / "models" / "goji-seg.onnx")
    ASSESS_MODEL_VERSION: str = "opencv-heuristic-v0"  # 换 YOLO 时改成 goji-seg-v1 等
    ASSESS_THRESHOLD_VERSION: str = "th-2026.10-01"
    ASSESS_MIN_IMAGE_CONF: float = 0.20   # 图级置信低于此值剔除
    ASSESS_GRAY_CONF: float = 0.45        # 低于此值 AI 不参与等级判定
    ASSESS_MIN_GRAINS: int = 20           # 样品总粒数代表性下限

    # ---------- 订单 ----------
    ORDER_CONFIRM_TIMEOUT_MIN: int = 1440  # 卖家确认超时（小时级演示用分钟配置）

    @property
    def is_prod(self) -> bool:
        return self.APP_ENV.lower() in {"prod", "production"}

    @property
    def cos_ready(self) -> bool:
        return bool(self.COS_SECRET_ID and self.COS_SECRET_KEY and self.COS_BUCKET)

    @property
    def llm_ready(self) -> bool:
        return bool(self.DASHSCOPE_API_KEY)

    def cos_public_url(self, key: str) -> str:
        return f"{self.COS_SCHEME}://{self.COS_DOMAIN}/{key.lstrip('/')}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
