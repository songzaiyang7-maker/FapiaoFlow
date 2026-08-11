"""单张发票完整处理流水线：PDF → 文本 → 字段 → 分类 → Invoice。"""

from __future__ import annotations

from pathlib import Path

from src.core.categories import CategoryStore
from src.core.config import load_config
from src.core.extractor import extract_fields
from src.core.hybrid_classifier import HybridClassifier
from src.core.parser import ParseError, extract_text
from src.core.types import Invoice

# 模块级缓存：避免每次处理 PDF 都重新加载 .env / categories / 初始化 OpenAI client
_default_classifier: HybridClassifier | None = None


def get_classifier() -> HybridClassifier:
    """获取默认分类器（hybrid，单例）。

    每次启动应用时第一次调用会加载 .env、categories.json、初始化 LLM client；
    后续调用直接返回缓存实例。
    """
    global _default_classifier
    if _default_classifier is None:
        _default_classifier = HybridClassifier(load_config(), CategoryStore().list())
    return _default_classifier


def reset_classifier() -> None:
    """重置缓存（设置/类目改动后调用）。"""
    global _default_classifier
    _default_classifier = None


def process_one_pdf(path: str | Path, classifier: HybridClassifier | None = None) -> Invoice:
    """处理一张发票 PDF，返回带全字段的 Invoice。

    classifier 为 None 时使用默认 hybrid 分类器。
    """
    p = Path(path)
    inv = Invoice(file_path=str(p), file_name=p.name)

    # 1. 提取 PDF 文本
    try:
        text = extract_text(p)
    except ParseError as e:
        inv.error = str(e)
        return inv

    if not text.strip():
        inv.error = "PDF 未提取到文本（可能是扫描件，本期暂不支持）"
        return inv

    inv.raw_text = text

    # 2. 提取结构化字段
    fields = extract_fields(text)
    inv.amount = fields.amount
    inv.invoice_no = fields.invoice_no
    inv.issue_date = fields.issue_date
    inv.seller_name = fields.seller_name

    if fields.amount is None:
        inv.error = "未找到价税合计金额"
        return inv

    # 3. 分类（hybrid：规则优先，低置信调 LLM）
    clf = classifier or get_classifier()
    category, confidence, note = clf.classify(inv)
    inv.category = category
    inv.confidence = confidence
    inv.note = note

    return inv


def reclassify(invoice: Invoice) -> None:
    """重新跑分类（用户撤回手动改类目时调用）。

    会清空 user_overridden 标记。
    """
    clf = get_classifier()
    category, confidence, note = clf.classify(invoice)
    invoice.category = category
    invoice.confidence = confidence
    invoice.note = note
    invoice.user_overridden = False
