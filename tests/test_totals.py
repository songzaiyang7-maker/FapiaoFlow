"""compute_totals / count_by_category 测试（配置驱动版）。"""

from __future__ import annotations

from src.core.categories import CategoryDef
from src.core.totals import compute_totals, count_by_category
from src.core.types import Invoice


def _cats() -> list[CategoryDef]:
    return [
        CategoryDef(name="差旅", priority=1),
        CategoryDef(name="材料", priority=2),
        CategoryDef(name="市内交通", priority=3),
        CategoryDef(name="其他", priority=99),
    ]


def _make(path: str, amount: float, cat: str) -> Invoice:
    return Invoice(file_path=path, file_name=path, amount=amount, category=cat)


def test_basic_grouping():
    """每类 1:1 独立汇总（无合并）。"""
    cats = _cats()
    invoices = [
        _make("a.pdf", 100.0, "市内交通"),
        _make("b.pdf", 200.0, "差旅"),
        _make("d.pdf", 300.0, "材料"),
        _make("e.pdf", 20.0, "其他"),
    ]
    totals = compute_totals(invoices, cats)
    assert totals["市内交通"] == 100.0
    assert totals["差旅"] == 200.0
    assert totals["材料"] == 300.0
    assert totals["其他"] == 20.0
    assert totals["总计"] == 620.0


def test_skip_none_amount_or_category():
    cats = _cats()
    invoices = [
        _make("a.pdf", 100.0, "市内交通"),
        Invoice(file_path="b.pdf", file_name="b.pdf", amount=None, category=None),
        Invoice(file_path="c.pdf", file_name="c.pdf", amount=50.0, category=None),
    ]
    totals = compute_totals(invoices, cats)
    assert totals["市内交通"] == 100.0
    assert totals["总计"] == 100.0


def test_deleted_category_goes_to_uncategorized():
    """类目被删但发票还指向它 → 归'未分类'，总额不丢。"""
    cats = _cats()
    invoices = [
        _make("a.pdf", 100.0, "市内交通"),
        _make("b.pdf", 500.0, "已删除的类目"),  # 这个类目不在 cats 里
    ]
    totals = compute_totals(invoices, cats)
    assert totals["市内交通"] == 100.0
    assert totals["未分类"] == 500.0
    assert totals["总计"] == 600.0  # 未分类也计入总计，不漏算钱


def test_count_by_category():
    cats = _cats()
    invoices = [
        _make("a.pdf", 1.0, "市内交通"),
        _make("b.pdf", 2.0, "市内交通"),
        _make("c.pdf", 3.0, "差旅"),
    ]
    counts = count_by_category(invoices, cats)
    assert counts["市内交通"] == 2
    assert counts["差旅"] == 1
    assert counts["材料"] == 0
    assert counts["其他"] == 0


def test_count_includes_uncategorized():
    """count_by_category 也统计未分类。"""
    cats = _cats()
    invoices = [
        _make("a.pdf", 1.0, "差旅"),
        _make("b.pdf", 2.0, "已删除"),
    ]
    counts = count_by_category(invoices, cats)
    assert counts["未分类"] == 1
    assert counts["差旅"] == 1
