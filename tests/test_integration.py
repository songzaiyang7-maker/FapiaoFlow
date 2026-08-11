"""端到端集成测试：合成 PDF → pipeline → 验证分类与汇总。

合成 PDF 使用 reportlab 模拟电子发票的关键文本布局。
真实电子发票的字体/坐标会更复杂，但只要文字能被 pdfplumber 提取，
我们的提取/分类逻辑就能工作。

注意：此测试强制使用 rule-only 分类器，避免真实调用 DeepSeek API。
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from src.core.categories import DEFAULT_CATEGORIES, CategoryDef
from src.core.config import LLMConfig
from src.core.hybrid_classifier import HybridClassifier
from src.core.pipeline import process_one_pdf
from src.core.totals import compute_totals


def _default_categories() -> list[CategoryDef]:
    """从 DEFAULT_CATEGORIES 构造（与生产配置一致）。"""
    return [CategoryDef.from_dict(d) for d in DEFAULT_CATEGORIES]


@pytest.fixture
def rule_only_classifier() -> HybridClassifier:
    """强制 rule-only，测试不调 API。"""
    cfg = LLMConfig(
        api_key=None,
        base_url="fake",
        model="fake",
        backend="rule",
        fallback_threshold=0.7,
    )
    return HybridClassifier(cfg, _default_categories())


def _make_pdf_bytes(lines: list[str]) -> bytes:
    """生成一个包含给定文本行的 PDF（使用 reportlab 内置 CJK 字体）。"""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    # STSong-Light 是 reportlab 内置的中文 CID 字体
    try:
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        c.setFont("STSong-Light", 10)
    except Exception:
        # 退回到默认字体（中文会变 nnnn，但英文/数字 OK）
        c.setFont("Helvetica", 10)
    y = 800
    for line in lines:
        c.drawString(50, y, line)
        y -= 14
    c.showPage()
    c.save()
    return buf.getvalue()


def _write_pdf(tmp_path: Path, name: str, lines: list[str]) -> Path:
    p = tmp_path / name
    p.write_bytes(_make_pdf_bytes(lines))
    return p


def test_hotel_invoice_classification(tmp_path: Path, rule_only_classifier):
    """酒店发票：销售方含'宾馆'，应归差旅。"""
    pdf = _write_pdf(tmp_path, "hotel.pdf", [
        "增值税电子普通发票",
        "发票号码: 24412000000000000001",
        "开票日期: 2026年08月10日",
        "销售方名称: 杭州西湖宾馆管理有限公司",
        "价税合计（大写） ⊙叁佰伍拾元整",
        "（小写） ￥350.00",
    ])
    inv = process_one_pdf(pdf, classifier=rule_only_classifier)
    assert inv.error is None, f"unexpected error: {inv.error}"
    assert inv.amount == pytest.approx(350.00)
    assert inv.category == "差旅"
    assert inv.invoice_no == "24412000000000000001"
    assert inv.issue_date == "2026-08-10"
    assert "西湖宾馆" in (inv.seller_name or "")


def test_didi_invoice_default_local(tmp_path: Path, rule_only_classifier):
    """滴滴发票：默认归市内交通，confidence=0.6（黄色待复核）。"""
    pdf = _write_pdf(tmp_path, "didi.pdf", [
        "增值税电子普通发票",
        "发票号码: 24412000000000000002",
        "开票日期: 2026-08-05",
        "销售方名称: 滴滴出行科技有限公司",
        "货物名称: 网约车服务",
        "价税合计（小写） ￥88.50",
    ])
    inv = process_one_pdf(pdf, classifier=rule_only_classifier)
    assert inv.error is None
    assert inv.amount == pytest.approx(88.50)
    assert inv.category == "市内交通"
    assert inv.confidence == 0.6
    assert inv.needs_review() is True  # 应该黄色提示


def test_non_invoice_pdf(tmp_path: Path, rule_only_classifier):
    """非发票 PDF：未找到价税合计，标记 error。"""
    pdf = _write_pdf(tmp_path, "random.pdf", [
        "这是一段普通文字，不是发票。",
        "没有价税合计，也没有 ¥ 金额。",
    ])
    inv = process_one_pdf(pdf, classifier=rule_only_classifier)
    assert inv.error is not None
    assert "价税合计" in inv.error or "未找到" in inv.error
    assert inv.amount is None
    assert inv.category is None


def test_batch_with_totals(tmp_path: Path, rule_only_classifier):
    """批量 3 张发票 + 汇总。"""
    cats = _default_categories()
    invoices_data = [
        ("a_hotel.pdf", [
            "销售方名称: 某酒店",
            "价税合计（小写） ￥500.00",
        ]),
        ("b_train.pdf", [
            "销售方名称: 中国铁路",
            "价税合计（小写） ￥1200.00",
        ]),
        ("b_didi.pdf", [
            "销售方名称: 滴滴出行",
            "货物名称: 网约车",
            "价税合计（小写） ￥45.00",
        ]),
    ]
    invoices = []
    for name, lines in invoices_data:
        p = _write_pdf(tmp_path, name, lines)
        invoices.append(process_one_pdf(p, classifier=rule_only_classifier))

    # 全部解析成功
    for inv in invoices:
        assert inv.error is None, f"{inv.file_name}: {inv.error}"

    totals = compute_totals(invoices, cats)
    assert totals["市内交通"] == 45.0   # 默认市内交通（用户可改室外）
    assert totals["差旅"] == 1700.0     # 500 + 1200
    assert totals["总计"] == 1745.0
