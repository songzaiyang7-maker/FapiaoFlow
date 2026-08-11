"""规则分类器：基于关键词字典把发票分到各类目。

业务规则（保留原设计意图）：
- 市内交通类（含出租/滴滴/公交/地铁关键词的类目）置信度给 0.6，提示用户复核
- 其他类目按命中数给 0.7/0.8/0.9
- 多类目命中时按 CategoryDef.priority 决定胜者

关键词来源：调用方传入的 list[CategoryDef]，不再模块级硬编码。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from src.core.categories import CategoryDef
from src.core.types import Invoice

# 类目名包含这些标识时，视为"本地交通类"，置信度降为 0.6（提示复核）
# 这样用户即使把类目改名成"本地打车"，仍能享受低置信度提示
_LOCAL_TRANSPORT_HINTS = ("交通", "出租", "打车", "出行", "公交", "地铁")


class ClassifierProtocol(Protocol):
    """分类器接口。LLM 兜底实现需满足此协议。"""

    def classify(self, invoice: Invoice) -> tuple[str, float, str]: ...


@dataclass
class _MatchResult:
    category: str
    hits: int
    priority: int


def _match_keywords(text: str, category: CategoryDef) -> int:
    """返回该类目关键词命中的次数。"""
    if not text or not category.keywords:
        return 0
    hits = 0
    for kw in category.keywords:
        if not kw:
            continue
        if kw in text:
            hits += 1
    return hits


def _score(hits: int) -> float:
    if hits <= 0:
        return 0.0
    if hits == 1:
        return 0.7
    if hits == 2:
        return 0.8
    return 0.9


def _is_local_transport_like(name: str) -> bool:
    """类目名是否像"本地交通类"（决定是否给 0.6 低置信度）。"""
    return any(hint in name for hint in _LOCAL_TRANSPORT_HINTS) and "差旅" not in name and "跨城" not in name


def classify_invoice(invoice: Invoice, categories: list[CategoryDef]) -> tuple[str, float, str]:
    """规则分类。返回 (category_name, confidence, note)。

    categories 应为 list（通常来自 CategoryStore.list()）。
    """
    text = invoice.raw_text or ""
    if invoice.seller_name:
        text_for_match = text + "\n" + invoice.seller_name
    else:
        text_for_match = text

    if not text_for_match.strip():
        # 文本为空，归到 priority 最大的类目（通常是"其他"）
        fallback = max(categories, key=lambda c: c.priority)
        return fallback.name, 0.3, "未提取到发票文本"

    candidates: list[_MatchResult] = []
    for cat in categories:
        if not cat.keywords:
            continue  # 无关键词的类目（如"其他"）不参与命中
        hits = _match_keywords(text_for_match, cat)
        if hits > 0:
            candidates.append(_MatchResult(category=cat.name, hits=hits, priority=cat.priority))

    if not candidates:
        fallback = max(categories, key=lambda c: c.priority)
        return fallback.name, 0.3, "未命中任何关键词"

    # 多类目冲突：按 priority 升序（数字越小越优先），priority 相同则按命中数降序
    if len(candidates) > 1:
        candidates.sort(key=lambda r: (r.priority, -r.hits))
        winner = candidates[0]
        loser_names = [c.category for c in candidates[1:]]
        note = f"命中多类目（{', '.join(loser_names)}），按优先级归{winner.category}"
        return winner.category, min(_score(winner.hits), 0.5), note

    winner = candidates[0]
    confidence = _score(winner.hits)
    note = f"关键词命中：{winner.category}"

    # 本地交通类发票给 0.6 低置信度（无法可靠判定是否本地，提示用户复核）
    if _is_local_transport_like(winner.category):
        confidence = 0.6
        note = "默认归此类；外地发票请手动改类目"

    return winner.category, confidence, note


class RuleClassifier:
    """ClassifierProtocol 的规则实现。构造时接收类目列表。"""

    def __init__(self, categories: list[CategoryDef]) -> None:
        self.categories = categories

    def classify(self, invoice: Invoice) -> tuple[str, float, str]:
        return classify_invoice(invoice, self.categories)
