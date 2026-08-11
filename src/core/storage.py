"""Session 持久化：JSON 文件存储。

文件位置：data/sessions.json（项目目录下，已加入 .gitignore）
结构：
    {
        "version": 1,
        "sessions": [
            { "id": "...", "date": "...", "label": "...", "invoices": [...] },
            ...
        ]
    }

操作：
- load() / save()  整体读写
- add_session() / remove_session() / update_session()

调用方应在每次变更后调用 save() 持久化。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from src.core.paths import get_data_dir
from src.core.types import Session

logger = logging.getLogger(__name__)


_FILE_VERSION = 1


def _default_file() -> Path:
    """延迟求值数据目录，避免 import 时就 mkdir（home 不可写时 import 会炸）。"""
    return get_data_dir() / "sessions.json"


class SessionStore:
    """Session 持久化。线程不安全——所有调用应在主线程。"""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or _default_file()
        self._sessions: list[Session] = []
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        self._sessions = self._read_file()

    def _read_file(self) -> list[Session]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            sessions_data = data.get("sessions", []) if isinstance(data, dict) else []
            # 逐个解析，单张损坏不影响其余 session（修原 #6 的连锁失败）
            sessions: list[Session] = []
            for i, s in enumerate(sessions_data):
                try:
                    sessions.append(Session.from_dict(s))
                except Exception as e:
                    logger.warning(f"第 {i} 条 session 解析失败（跳过）: {e}")
            return sessions
        except json.JSONDecodeError as e:
            logger.warning(f"sessions.json 不是合法 JSON（当作空文件处理）: {e}")
            return []
        except Exception as e:
            logger.warning(f"读取 sessions.json 失败（当作空文件处理）: {e}")
            return []

    def _write_file(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": _FILE_VERSION,
            "sessions": [s.to_dict() for s in self._sessions],
        }
        # 写到临时文件再 rename，避免崩溃导致文件损坏
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    # --- 读 API ---
    def list_sessions(self) -> list[Session]:
        """按 (date, id) 复合降序返回（最近的最前；同 date 用 id 保证全序确定）。"""
        self._ensure_loaded()
        return sorted(self._sessions, key=lambda s: (s.date, s.id), reverse=True)

    def get_session(self, session_id: str) -> Session | None:
        self._ensure_loaded()
        for s in self._sessions:
            if s.id == session_id:
                return s
        return None

    # --- 写 API ---
    def save_session(self, session: Session) -> None:
        """新增或更新 session。"""
        self._ensure_loaded()
        for i, s in enumerate(self._sessions):
            if s.id == session.id:
                self._sessions[i] = session
                break
        else:
            self._sessions.append(session)
        self._write_file()

    def remove_session(self, session_id: str) -> bool:
        self._ensure_loaded()
        before = len(self._sessions)
        self._sessions = [s for s in self._sessions if s.id != session_id]
        removed = len(self._sessions) < before
        if removed:
            self._write_file()
        return removed

    @staticmethod
    def new_session(label: str = "") -> Session:
        """创建一个新 Session，date 自动填今天。"""
        return Session(
            date=datetime.now().strftime("%Y-%m-%d"),
            label=label,
        )
