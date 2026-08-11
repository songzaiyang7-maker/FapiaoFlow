"""配置加载：从 .env 读取 LLM 相关设置。

不强制要求 .env 存在——纯规则模式下不需要 API key。
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


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


def load_config() -> LLMConfig:
    """加载 .env，返回 LLMConfig。

    打包模式下从 ~/.fapiaoflow/.env 加载；开发模式从项目根目录的 .env 加载。
    文件不存在时直接用环境变量/默认值（不向上搜索父目录，避免误读）。
    """
    from src.core.paths import get_env_path

    env_path = get_env_path()
    if env_path.exists():
        load_dotenv(env_path)

    return LLMConfig(
        api_key=os.environ.get("DEEPSEEK_API_KEY") or None,
        base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        model=os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
        backend=os.environ.get("CLASSIFIER_BACKEND", "hybrid"),
        fallback_threshold=float(os.environ.get("LLM_FALLBACK_THRESHOLD", "0.7")),
    )
