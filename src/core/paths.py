"""路径解析：开发模式 vs PyInstaller 打包模式。

- 开发模式（python main.py）：data/ 在项目根目录
- 打包模式（exe）：数据放 ~/.fapiaoflow/，独立于 exe 位置

这样 exe 可以放任何位置，删 exe 不会丢数据，多版本共用同一份数据。
"""

from __future__ import annotations

import sys
from pathlib import Path

APP_DIR_NAME = ".fapiaoflow"


def is_frozen() -> bool:
    """是否运行在 PyInstaller 打包的 exe 里。"""
    return getattr(sys, "frozen", False)


def get_data_dir() -> Path:
    """数据目录（sessions.json 等）。"""
    if is_frozen():
        d = Path.home() / APP_DIR_NAME
    else:
        # src/core/paths.py → 项目根目录 / data
        d = Path(__file__).resolve().parent.parent.parent / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_env_path() -> Path:
    """.env 文件路径。

    打包模式：~/.fapiaoflow/.env（用户可手动放）
    开发模式：项目根目录 / .env
    """
    if is_frozen():
        return Path.home() / APP_DIR_NAME / ".env"
    return Path(__file__).resolve().parent.parent.parent / ".env"
