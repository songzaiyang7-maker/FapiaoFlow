"""按类目汇总金额。

每类 1:1 独立汇总（不再有"市外交通合并到差旅"的合并规则——
自定义类目后合并规则会变复杂，1 类 = 1 列最简单清晰）。

类目被删除但旧发票仍指向它时，归入"未分类"桶并记 warning（修原 #5）。
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

from src.core.categories import CategoryDef
from src.core.types import Invoice

logger = logging.getLogger(__name__)


def compute_totals(
    invoices: Iterable[Invoice],
    categories: list[CategoryDef],
) -> dict[str, float]:
    """计算各类目小计与总计。

    返回示例：
        {
            "差旅": 1630.0,
            "材料": 0.0,
            "市内交通": 45.0,
            "其他": 0.0,
            "未分类": 0.0,    # 类目被删但发票仍指向它时归此
            "总计": 1675.0,
        }

    categories 决定输出 dict 的 key 顺序（按 priority 升序）。
    """
    # 按 priority 升序构建类目桶
    sorted_cats = sorted(categories, key=lambda c: (c.priority, c.name))
    valid_names = {c.name for c in sorted_cats}
    totals: dict[str, float] = {c.name: 0.0 for c in sorted_cats}
    totals["未分类"] = 0.0
    totals["总计"] = 0.0

    has_uncategorized = False
    for inv in invoices:
        if inv.amount is None or inv.category is None:
            continue
        if inv.category in valid_names:
            totals[inv.category] += inv.amount
        else:
            # 类目被删但发票还指向它——归"未分类"，避免金额被静默丢弃
            totals["未分类"] += inv.amount
            has_uncategorized = True

    if has_uncategorized:
        logger.warning(
            "发现发票指向不存在的类目，已归入'未分类'桶。"
            "建议在类目管理中处理这些发票。"
        )

    # 总计 = 所有可见类目 + 未分类（未分类也参与总计，不漏算钱）
    totals["总计"] = sum(totals[c.name] for c in sorted_cats) + totals["未分类"]
    return totals


def count_by_category(
    invoices: Iterable[Invoice],
    categories: list[CategoryDef],
) -> dict[str, int]:
    """各类目的发票张数（用于 UI 统计栏）。

    返回的 dict 包含所有传入的类目（值为 0 也在），加上"未分类"桶。
    """
    sorted_cats = sorted(categories, key=lambda c: (c.priority, c.name))
    valid_names = {c.name for c in sorted_cats}
    counts: dict[str, int] = {c.name: 0 for c in sorted_cats}
    counts["未分类"] = 0
    for inv in invoices:
        if inv.category is None:
            continue
        if inv.category in valid_names:
            counts[inv.category] += 1
        else:
            counts["未分类"] += 1
    return counts
