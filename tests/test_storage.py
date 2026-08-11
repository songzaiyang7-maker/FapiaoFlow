"""SessionStore 测试：roundtrip + 排序 + 损坏恢复 + 类目改名兼容。

重点验证原 CRITICAL #6：类目改名后旧数据不炸库。
"""

from __future__ import annotations

import json
from pathlib import Path

from src.core.storage import SessionStore
from src.core.types import Invoice, Session


def _make_session(date: str = "2026-08-10", label: str = "", invoices=None) -> Session:
    return Session(
        id="test123",
        date=date,
        label=label,
        invoices=invoices or [],
    )


def test_roundtrip(tmp_path: Path):
    """save → load 应保持数据一致。"""
    path = tmp_path / "sessions.json"
    store = SessionStore(path=path)
    inv = Invoice(
        file_path="a.pdf", file_name="a.pdf",
        amount=100.0, category="差旅",
        seller_name="某酒店", invoice_no="12345678901234567890",
        issue_date="2026-08-10", confidence=0.8, note="关键词命中：差旅",
    )
    s = _make_session(label="出差", invoices=[inv])
    store.save_session(s)

    # 新 store 实例读取
    store2 = SessionStore(path=path)
    loaded = store2.list_sessions()
    assert len(loaded) == 1
    assert loaded[0].id == "test123"
    assert loaded[0].label == "出差"
    assert len(loaded[0].invoices) == 1
    assert loaded[0].invoices[0].category == "差旅"
    assert loaded[0].invoices[0].amount == 100.0


def test_category_rename_does_not_crash(tmp_path: Path):
    """类目改名后旧数据应能正常加载（修原 CRITICAL #6）。

    category 现在是字符串，不再做 Category(...) 转换，
    所以"差旅"被改成"出差"后，旧记录里的"差旅"仍能读出来（只是变成无效类目）。
    """
    path = tmp_path / "sessions.json"
    store = SessionStore(path=path)
    inv = Invoice(file_path="a.pdf", file_name="a.pdf", amount=100.0, category="差旅")
    store.save_session(_make_session(invoices=[inv]))

    # 直接读回（category 是任意字符串，不抛异常）
    store2 = SessionStore(path=path)
    loaded = store2.list_sessions()
    assert len(loaded) == 1
    assert loaded[0].invoices[0].category == "差旅"  # 旧字符串保留


def test_corrupted_json_returns_empty(tmp_path: Path):
    """损坏的 JSON 文件应返回空列表，不抛异常。"""
    path = tmp_path / "sessions.json"
    path.write_text("{这不是合法的json", encoding="utf-8")
    store = SessionStore(path=path)
    loaded = store.list_sessions()
    assert loaded == []


def test_partial_corruption_skips_bad_session(tmp_path: Path):
    """单条 session 损坏不应影响其他 session（修原 #6 的连锁失败）。"""
    path = tmp_path / "sessions.json"
    # 构造一个有 2 条 session 的文件，第一条合法，第二条缺 id（结构异常）
    data = {
        "version": 1,
        "sessions": [
            {"id": "good1", "date": "2026-08-10", "label": "好", "invoices": []},
            {"date": "2026-08-09", "invoices": [{"category": "差旅"}]},  # 缺 file_path
        ],
    }
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    store = SessionStore(path=path)
    loaded = store.list_sessions()
    # 第一条应能加载，第二条因 Invoice 需要 file_path 会失败但被跳过
    assert len(loaded) >= 1
    assert loaded[0].id == "good1"


def test_sorting_stability(tmp_path: Path):
    """同 date 的多个 session 排序应确定（修原 #7）。"""
    path = tmp_path / "sessions.json"
    store = SessionStore(path=path)
    # 三个同日 session，不同 id
    for i, sid in enumerate(["aaa", "bbb", "ccc"]):
        s = Session(id=sid, date="2026-08-10", label=f"session{i}", invoices=[])
        store.save_session(s)
    loaded = store.list_sessions()
    # 同 date 按 id 降序（reverse=True）
    assert [s.id for s in loaded] == ["ccc", "bbb", "aaa"]


def test_remove_session(tmp_path: Path):
    path = tmp_path / "sessions.json"
    store = SessionStore(path=path)
    store.save_session(Session(id="keep", date="2026-08-10"))
    store.save_session(Session(id="del", date="2026-08-09"))
    assert store.remove_session("del") is True
    assert store.remove_session("not_exist") is False
    loaded = store.list_sessions()
    assert len(loaded) == 1
    assert loaded[0].id == "keep"
