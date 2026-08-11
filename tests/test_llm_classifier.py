"""LLM 分类器与 Hybrid 分类器测试（配置驱动版）。

为避免消耗 API 费用，单元测试用 mock。
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from src.core.categories import CategoryDef
from src.core.config import LLMConfig
from src.core.hybrid_classifier import HybridClassifier
from src.core.llm_classifier import LLMClassifier
from src.core.types import Invoice


def _categories() -> list[CategoryDef]:
    return [
        CategoryDef(name="差旅", keywords=["酒店", "航空"], priority=1),
        CategoryDef(name="材料", keywords=["仪器", "办公"], priority=2),
        CategoryDef(name="市内交通", keywords=["出租", "滴滴"], priority=3),
        CategoryDef(name="其他", keywords=[], priority=99),
    ]


def _make_invoice(text: str = "酒店", seller: str = "某宾馆") -> Invoice:
    return Invoice(
        file_path="x.pdf",
        file_name="x.pdf",
        raw_text=text,
        seller_name=seller,
        amount=100.0,
    )


# ---------- LLMClassifier ----------


def _mock_openai_response(content: str):
    """构造一个最小的 mock chat completion response。"""
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = content
    return resp


def test_llm_parses_valid_json():
    llm = LLMClassifier(api_key="fake", base_url="fake", model="fake", categories=_categories())
    with patch.object(llm.client, "chat") as mock_chat:
        mock_chat.completions.create.return_value = _mock_openai_response(
            json.dumps({"category": "差旅", "reason": "销售方是酒店"})
        )
        result = llm.classify(_make_invoice())
    assert result is not None
    cat, conf, note = result
    assert cat == "差旅"
    assert conf == 0.95
    assert "酒店" in note


def test_llm_handles_invalid_category():
    """LLM 返回不存在的类目 → 返回 None。"""
    llm = LLMClassifier(api_key="fake", base_url="fake", model="fake", categories=_categories())
    with patch.object(llm.client, "chat") as mock_chat:
        mock_chat.completions.create.return_value = _mock_openai_response(
            json.dumps({"category": "火车票", "reason": "无效类目"})
        )
        result = llm.classify(_make_invoice())
    assert result is None


def test_llm_handles_malformed_json():
    """LLM 返回非 JSON → 返回 None。"""
    llm = LLMClassifier(api_key="fake", base_url="fake", model="fake", categories=_categories())
    with patch.object(llm.client, "chat") as mock_chat:
        mock_chat.completions.create.return_value = _mock_openai_response("not a json")
        result = llm.classify(_make_invoice())
    assert result is None


def test_llm_handles_api_exception():
    """API 调用抛异常 → 返回 None。"""
    llm = LLMClassifier(api_key="fake", base_url="fake", model="fake", categories=_categories())
    with patch.object(llm.client, "chat") as mock_chat:
        mock_chat.completions.create.side_effect = RuntimeError("network error")
        result = llm.classify(_make_invoice())
    assert result is None


def test_llm_timeout_passed_to_client():
    """timeout 参数应传给 OpenAI client（修原 #8）。"""
    llm = LLMClassifier(
        api_key="fake", base_url="fake", model="fake",
        categories=_categories(), timeout=42.0,
    )
    assert llm.client.timeout == 42.0


def test_llm_prompt_includes_custom_categories():
    """动态 prompt 应包含当前所有类目名。"""
    from src.core.llm_classifier import build_system_prompt
    prompt = build_system_prompt(_categories())
    for name in ["差旅", "材料", "市内交通", "其他"]:
        assert name in prompt


# ---------- HybridClassifier ----------


def test_hybrid_rule_only_backend():
    """backend=rule：永不调 LLM。"""
    cfg = LLMConfig(
        api_key="fake", base_url="fake", model="fake",
        backend="rule", fallback_threshold=0.7,
    )
    clf = HybridClassifier(cfg, _categories())
    assert clf._llm is None  # rule 模式不应初始化 LLM

    # 高置信度命中差旅
    inv = _make_invoice(text="酒店", seller="某酒店")
    cat, conf, _ = clf.classify(inv)
    assert cat == "差旅"


def test_hybrid_llm_fallback_on_low_confidence():
    """hybrid：规则置信度低 → 调 LLM。"""
    cfg = LLMConfig(
        api_key="fake", base_url="fake", model="fake",
        backend="hybrid", fallback_threshold=0.7,
    )
    clf = HybridClassifier(cfg, _categories())
    with patch.object(clf._llm.client, "chat") as mock_chat:
        mock_chat.completions.create.return_value = _mock_openai_response(
            json.dumps({"category": "材料", "reason": "实验仪器采购"})
        )
        # 用一个低置信度发票（市内交通默认 0.6）
        inv = _make_invoice(text="出租", seller="某出租公司")
        cat, conf, note = clf.classify(inv)
    assert cat == "材料"
    assert "LLM" in note


def test_hybrid_skips_llm_when_high_confidence():
    """hybrid：规则置信度高 → 不调 LLM。"""
    cfg = LLMConfig(
        api_key="fake", base_url="fake", model="fake",
        backend="hybrid", fallback_threshold=0.7,
    )
    clf = HybridClassifier(cfg, _categories())
    with patch.object(clf._llm.client, "chat") as mock_chat:
        mock_chat.completions.create.return_value = _mock_openai_response(
            json.dumps({"category": "其他"})
        )
        # 命中差旅，conf=0.8（单关键词）
        inv = _make_invoice(text="酒店", seller="某酒店")
        cat, conf, note = clf.classify(inv)
        # LLM 没被调用
        mock_chat.completions.create.assert_not_called()
    assert cat == "差旅"
    assert "差旅" in note or "命中" in note


def test_hybrid_falls_back_when_llm_fails():
    """hybrid：LLM 调用失败 → 沿用规则结果，但置信度降低。"""
    cfg = LLMConfig(
        api_key="fake", base_url="fake", model="fake",
        backend="hybrid", fallback_threshold=0.7,
    )
    clf = HybridClassifier(cfg, _categories())
    with patch.object(clf._llm.client, "chat") as mock_chat:
        mock_chat.completions.create.side_effect = RuntimeError("network")
        # 低置信度（市内交通 0.6），会调 LLM，LLM 失败
        inv = _make_invoice(text="出租", seller="某出租公司")
        cat, conf, note = clf.classify(inv)
    # 沿用规则的市内交通
    assert cat == "市内交通"
    # 置信度被限制到 0.5
    assert conf == 0.5
    assert "LLM 失败" in note


def test_hybrid_no_api_key_uses_rule_only():
    """没配 API key → 自动降级为纯规则。"""
    cfg = LLMConfig(
        api_key=None, base_url="fake", model="fake",
        backend="hybrid", fallback_threshold=0.7,
    )
    clf = HybridClassifier(cfg, _categories())
    assert clf._llm is None

    inv = _make_invoice(text="出租", seller="某出租公司")
    cat, conf, note = clf.classify(inv)
    assert cat == "市内交通"
    assert "LLM 未配置" in note


def test_hybrid_llm_only_backend():
    """backend=llm：始终用 LLM（即使规则置信度高）。"""
    cfg = LLMConfig(
        api_key="fake", base_url="fake", model="fake",
        backend="llm", fallback_threshold=0.7,
    )
    clf = HybridClassifier(cfg, _categories())
    with patch.object(clf._llm.client, "chat") as mock_chat:
        mock_chat.completions.create.return_value = _mock_openai_response(
            json.dumps({"category": "差旅", "reason": "住宿"})
        )
        inv = _make_invoice(text="酒店", seller="某酒店")
        cat, conf, note = clf.classify(inv)
        mock_chat.completions.create.assert_called_once()
    assert cat == "差旅"
    assert "LLM" in note
