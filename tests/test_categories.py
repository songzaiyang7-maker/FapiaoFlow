"""CategoryStore 测试：加载/保存/增删改/默认配置。"""

from __future__ import annotations

import json
from pathlib import Path

from src.core.categories import CategoryDef, CategoryStore


def test_default_categories_loaded(tmp_path: Path):
    """首次运行：文件不存在时写入默认配置。"""
    path = tmp_path / "categories.json"
    store = SessionStore_safe(path)
    cats = store.list()
    assert len(cats) == 4
    names = [c.name for c in cats]
    assert "差旅" in names
    assert "其他" in names
    # 文件应已被创建
    assert path.exists()


def test_roundtrip(tmp_path: Path):
    """save → 重新加载保持一致。"""
    path = tmp_path / "categories.json"
    store = SessionStore_safe(path)
    store.add("新类目", keywords=["关键词1", "关键词2"], color="#abcdef")
    store.save()

    store2 = SessionStore_safe(path)
    cats = store2.list()
    names = [c.name for c in cats]
    assert "新类目" in names
    new_cat = store2.get("新类目")
    assert new_cat is not None
    assert new_cat.keywords == ["关键词1", "关键词2"]
    assert new_cat.color == "#abcdef"


def test_add_duplicate_returns_false(tmp_path: Path):
    path = tmp_path / "categories.json"
    store = SessionStore_safe(path)
    assert store.add("差旅") is False  # 已存在


def test_add_empty_name_returns_false(tmp_path: Path):
    path = tmp_path / "categories.json"
    store = SessionStore_safe(path)
    assert store.add("   ") is False


def test_remove(tmp_path: Path):
    path = tmp_path / "categories.json"
    store = SessionStore_safe(path)
    assert store.remove("材料") is True
    assert store.remove("不存在") is False
    assert store.get("材料") is None


def test_rename(tmp_path: Path):
    path = tmp_path / "categories.json"
    store = SessionStore_safe(path)
    assert store.rename("差旅", "出差") is True
    assert store.get("出差") is not None
    assert store.get("差旅") is None
    # 改成已存在的名字应失败
    assert store.rename("出差", "其他") is False


def test_rename_to_empty_returns_false(tmp_path: Path):
    path = tmp_path / "categories.json"
    store = SessionStore_safe(path)
    assert store.rename("差旅", "") is False


def test_update_keywords_color_priority(tmp_path: Path):
    path = tmp_path / "categories.json"
    store = SessionStore_safe(path)
    assert store.update("差旅", keywords=["新词"], color="#123456", priority=5) is True
    cat = store.get("差旅")
    assert cat.keywords == ["新词"]
    assert cat.color == "#123456"
    assert cat.priority == 5


def test_replace_all(tmp_path: Path):
    """整体替换（类目管理对话框"确定"时用）。"""
    path = tmp_path / "categories.json"
    store = SessionStore_safe(path)
    new_cats = [
        CategoryDef(name="A", priority=1),
        CategoryDef(name="B", priority=2),
        CategoryDef(name="C", priority=3),
    ]
    store.replace_all(new_cats)
    store.save()
    cats = store.list()
    assert [c.name for c in cats] == ["A", "B", "C"]


def test_corrupted_file_falls_back_to_default(tmp_path: Path):
    """损坏的 categories.json 应回退默认配置。"""
    path = tmp_path / "categories.json"
    path.write_text("这不是合法json", encoding="utf-8")
    store = SessionStore_safe(path)
    cats = store.list()
    assert len(cats) == 4  # 默认 4 类


def test_empty_categories_file_falls_back(tmp_path: Path):
    """空的 categories 列表应回退默认。"""
    path = tmp_path / "categories.json"
    path.write_text(json.dumps({"version": 1, "categories": []}), encoding="utf-8")
    store = SessionStore_safe(path)
    cats = store.list()
    assert len(cats) == 4


def test_load_legacy_list_format(tmp_path: Path):
    """兼容旧格式：顶层直接是 list。"""
    path = tmp_path / "categories.json"
    path.write_text(json.dumps([
        {"name": "X", "keywords": ["x"], "color": "#fff", "priority": 1},
    ]), encoding="utf-8")
    store = SessionStore_safe(path)
    cats = store.list()
    assert len(cats) == 1
    assert cats[0].name == "X"


# 辅助：避免 _ensure_loaded 时写默认文件污染断言
def SessionStore_safe(path: Path) -> CategoryStore:
    """构造一个指定路径的 CategoryStore，确保每次都重新读文件。"""
    return CategoryStore(path=path)
