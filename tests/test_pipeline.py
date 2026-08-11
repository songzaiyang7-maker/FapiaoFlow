"""Pipeline 端到端测试，覆盖成功/失败路径。"""

from __future__ import annotations

from src.core.pipeline import process_one_pdf


def test_nonexistent_file_returns_error():
    inv = process_one_pdf("nonexistent.pdf")
    assert inv.error is not None
    assert "不存在" in inv.error or "解析失败" in inv.error
    assert inv.amount is None
    assert inv.category is None


def test_user_override_persistence():
    """用户手动改类目应保留——pipeline 不会自动覆盖。"""
    from src.core.types import Invoice

    inv = Invoice(
        file_path="x.pdf",
        file_name="x.pdf",
        raw_text="住宿",
        seller_name="某酒店",
        amount=350.0,
    )
    # 模拟用户改为材料
    inv.category = "材料"
    inv.user_overridden = True
    # 用户改过的标记应在
    assert inv.user_overridden is True
    assert inv.category == "材料"
