"""金额提取单元测试，覆盖典型电子发票文本片段。"""

from __future__ import annotations

import pytest

from src.utils.amount import extract_amount


def test_standard_jiashuiheji():
    """标准格式：价税合计行带 ￥ 小写金额。"""
    text = (
        "价税合计（大写） ⊙壹仟贰佰叁拾肆元伍角陆分\n"
        "（小写） ￥1234.56"
    )
    assert extract_amount(text) == pytest.approx(1234.56)


def test_full_width_yen():
    """全角 ￥ 符号。"""
    text = "价税合计（大写）X圆整　（小写）￥9,876.00"
    assert extract_amount(text) == pytest.approx(9876.00)


def test_thousands_separator():
    """千分位逗号。"""
    text = "价税合计（小写） ￥1,234,567.89"
    assert extract_amount(text) == pytest.approx(1234567.89)


def test_extra_whitespace():
    """￥ 与数字间有空格或全角空格。"""
    text = "价税合计（小写） ￥  88.50"
    assert extract_amount(text) == pytest.approx(88.50)


def test_xiaoxie_fallback():
    """没有'价税合计'字样，但有'（小写）'。"""
    text = "随便什么内容\n（小写） ￥42.00\n其他"
    assert extract_amount(text) == pytest.approx(42.00)


def test_amount_only_fallback():
    """连'小写'都没有，只剩多个 ￥ 金额——取最大值。"""
    text = "税额 ￥10.00\n金额 ￥90.00\n其他 ￥5.00"
    # 没有价税合计/小写，所有金额走 max 兜底
    assert extract_amount(text) == pytest.approx(90.00)


def test_empty_text():
    assert extract_amount("") is None
    assert extract_amount(None) is None  # type: ignore[arg-type]


def test_no_amount():
    text = "这是一段不含金额的文本。"
    assert extract_amount(text) is None


def test_malformed_amount_skipped():
    """非数字金额被忽略，不抛异常。"""
    text = "￥abc.XX\n价税合计（小写） ￥100.00"
    assert extract_amount(text) == pytest.approx(100.00)


def test_negative_amount_jiashuiheji():
    """红字发票（价税合计为负）——修原 #17。"""
    text = "价税合计（大写）X圆整　（小写）￥-14.38"
    assert extract_amount(text) == pytest.approx(-14.38)


def test_negative_amount_xiaoxie():
    """红字发票（小写标记为负）。"""
    text = "（小写） ￥-100.00"
    assert extract_amount(text) == pytest.approx(-100.00)


def test_full_negative_invoice():
    """完整红字发票：价税合计行带负数。"""
    text = (
        "增值税电子普通发票\n"
        "销售方名称: 某酒店\n"
        "价税合计（大写） ⊙负壹拾肆元叁角捌分\n"
        "（小写） ￥-14.38"
    )
    assert extract_amount(text) == pytest.approx(-14.38)
