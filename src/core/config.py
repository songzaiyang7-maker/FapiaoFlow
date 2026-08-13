"""配置加载：从 .env 读取 LLM 和 OCR 相关设置。

不强制要求 .env 存在——纯规则模式下不需要 API key，OCR 不可用时自动降级。
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass
class AppConfig:
    """应用全局配置。"""
    llm: LLMConfig
    ocr_enabled: bool = True  # 是否对扫描件做 OCR（关闭可省内存）


@dataclass
class LLMConfig:
    api_key: str | None
    base_url: str
    model: str
    backend: str          # "rule" | "llm" | "hybrid"
    fallback_threshold: float  # 低于此置信度调 LLM

    @property
    def is_available(self) -> bool:
        return bool(self.api_key) and self.backend in ("llm", "hybrid")


def load_llm_config() -> LLMConfig:
    """加载 .env，返回 LLMConfig。

    打包模式下从 ~/.fapiaoflow/.env 加载；开发模式从项目根目录的 .env 加载。
    文件不存在时直接用环境变量/默认值（不向上搜索父目录，避免误读）。
    """
    _load_env()
    return LLMConfig(
        api_key=os.environ.get("DEEPSEEK_API_KEY") or None,
        base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        model=os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
        backend=os.environ.get("CLASSIFIER_BACKEND", "hybrid"),
        fallback_threshold=float(os.environ.get("LLM_FALLBACK_THRESHOLD", "0.7")),
    )


def load_ocr_enabled() -> bool:
    """读取 OCR 开关配置。默认开启。"""
    _load_env()
    return os.environ.get("OCR_ENABLED", "true").lower() in ("true", "1", "yes")


def _load_env() -> None:
    """加载 .env（内部复用，避免重复加载逻辑）。"""
    from src.core.paths import get_env_path
    env_path = get_env_path()
    if env_path.exists():
        load_dotenv(env_path)


# 向后兼容：原 load_config 改名了，保留旧接口
def load_config() -> LLMConfig:
    """向后兼容别名，等同 load_llm_config()。"""
    return load_llm_config()
