"""类目配置：用户可自由增删改的发票分类体系。

类目定义持久化到 data/categories.json（打包后 ~/.fapiaoflow/categories.json）。
首次运行写入默认 4 类。用户可通过"设置 → 类目管理"对话框编辑。

类目结构：
    {
        "name": "差旅",
        "keywords": ["航空", "机票", "酒店", ...],
        "color": "#e3f2fd",
        "priority": 1
    }

- name:      显示名，也是 Invoice.category 存的值（字符串）
- keywords:  规则分类器匹配用的关键词列表
- color:     GUI 拖拽按钮的背景色（柔和卡片色）
- priority:  多类目冲突时的优先级（数字越小越优先）
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path

from src.core.paths import get_data_dir

logger = logging.getLogger(__name__)


# 默认配色：与原 category_drop.py 的 BUTTONS 保持一致，保证老用户视觉无变化
DEFAULT_CATEGORIES: list[dict] = [
    {
        "name": "差旅",
        "keywords": [
            # 跨城交通
            "航空", "机票", "航班", "行程单", "机场", "民航",
            "铁路", "高铁", "火车", "动车", "车站", "客运",
            # 住宿
            "酒店", "宾馆", "旅馆", "住宿", "民宿", "公寓", "招待所", "度假村", "饭店",
        ],
        "color": "#e3f2fd",
        "priority": 1,
    },
    {
        "name": "材料",
        "keywords": [
            "商贸", "办公", "书店", "材料", "实验室", "仪器",
            "试剂", "电脑", "打印机", "文具", "耗材", "图书",
            "玻璃仪器", "化学",
        ],
        "color": "#fff3e0",
        "priority": 2,
    },
    {
        "name": "市内交通",
        "keywords": [
            "出租", "网约车", "滴滴", "神州", "曹操出行", "公交", "地铁",
            "轨道交通", "共享单车", "停车", "哈啰", "美团打车",
        ],
        "color": "#e8f5e9",
        "priority": 3,
    },
    {
        "name": "其他",
        "keywords": [],
        "color": "#f3e5f5",
        "priority": 99,
    },
]


@dataclass
class CategoryDef:
    """单个类目的定义。"""

    name: str
    keywords: list[str] = field(default_factory=list)
    color: str = "#f3e5f5"
    priority: int = 99

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> CategoryDef:
        return cls(
            name=str(d.get("name", "")).strip(),
            keywords=[str(k).strip() for k in d.get("keywords", []) if str(k).strip()],
            color=str(d.get("color", "#f3e5f5")),
            priority=int(d.get("priority", 99)),
        )


def _default_file() -> Path:
    return get_data_dir() / "categories.json"


class CategoryStore:
    """类目的加载/保存/编辑。

    所有操作都是即时的——调用方负责在合适时机调用 save() 持久化。
    线程不安全，所有调用应在主线程。
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or _default_file()
        self._categories: list[CategoryDef] = []
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        self._categories = self._read_file()

    def _read_file(self) -> list[CategoryDef]:
        if not self.path.exists():
            # 首次运行：写入默认配置
            cats = [CategoryDef.from_dict(d) for d in DEFAULT_CATEGORIES]
            self._categories = cats
            try:
                self._write_file()
            except OSError as e:
                logger.warning(f"首次写入默认 categories.json 失败: {e}")
            return cats
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                # 兼容 {"categories": [...]} 或 {"version":1, "categories":[...]}
                items = data.get("categories", [])
            elif isinstance(data, list):
                items = data
            else:
                items = []
            cats = [CategoryDef.from_dict(d) for d in items if isinstance(d, dict)]
            if not cats:
                logger.warning("categories.json 为空，回退默认配置")
                return [CategoryDef.from_dict(d) for d in DEFAULT_CATEGORIES]
            return cats
        except Exception as e:
            logger.warning(f"读取 categories.json 失败（回退默认配置）: {e}")
            return [CategoryDef.from_dict(d) for d in DEFAULT_CATEGORIES]

    def _write_file(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": 1,
            "categories": [c.to_dict() for c in self._categories],
        }
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    # --- 读 API ---
    def list(self) -> list[CategoryDef]:
        """返回所有类目（按 priority 升序）。"""
        self._ensure_loaded()
        return sorted(self._categories, key=lambda c: (c.priority, c.name))

    def names(self) -> list[str]:
        """类目名列表（按 priority 升序）。"""
        return [c.name for c in self.list()]

    def get(self, name: str) -> CategoryDef | None:
        self._ensure_loaded()
        for c in self._categories:
            if c.name == name:
                return c
        return None

    # --- 写 API ---
    def save(self) -> None:
        """持久化到文件。"""
        self._ensure_loaded()
        self._write_file()

    def add(self, name: str, keywords: list[str] | None = None,
            color: str = "#f3e5f5", priority: int | None = None) -> bool:
        """新增类目。name 重名返回 False。"""
        self._ensure_loaded()
        if not name.strip():
            return False
        if self.get(name):
            return False
        if priority is None:
            # 默认放到已有非"其他"类目之后、"其他"之前
            existing = [c.priority for c in self._categories if c.priority < 90]
            priority = (max(existing) + 1) if existing else len(self._categories) + 1
        self._categories.append(CategoryDef(
            name=name.strip(),
            keywords=list(keywords or []),
            color=color,
            priority=priority,
        ))
        return True

    def remove(self, name: str) -> bool:
        """删除类目。返回是否实际删除。"""
        self._ensure_loaded()
        before = len(self._categories)
        self._categories = [c for c in self._categories if c.name != name]
        return len(self._categories) < before

    def rename(self, old: str, new: str) -> bool:
        """类目改名。new 重名或 old 不存在返回 False。"""
        self._ensure_loaded()
        new = new.strip()
        if not new:
            return False
        if new != old and self.get(new):
            return False
        c = self.get(old)
        if c is None:
            return False
        c.name = new
        return True

    def update(self, name: str, keywords: list[str] | None = None,
               color: str | None = None, priority: int | None = None) -> bool:
        """更新类目属性。任一参数为 None 表示不改。"""
        self._ensure_loaded()
        c = self.get(name)
        if c is None:
            return False
        if keywords is not None:
            c.keywords = list(keywords)
        if color is not None:
            c.color = color
        if priority is not None:
            c.priority = priority
        return True

    def replace_all(self, categories: list[CategoryDef]) -> None:
        """整体替换（类目管理对话框"确定"时用）。"""
        self._ensure_loaded()  # 确保 _loaded=True，避免 save() 时重新读文件覆盖
        self._categories = list(categories)
