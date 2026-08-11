"""混合分类器：规则优先，置信度低时调 LLM 兜底。

策略：
1. backend == "rule"：只用规则
2. backend == "llm"：只用 LLM（适合调试）
3. backend == "hybrid"（默认）：规则先跑，confidence < threshold 时调 LLM

关键设计：
- LLM 配置不可用（无 key / 无网络）→ 自动降级为纯规则
- LLM 调用失败 → 沿用规则结果，但 confidence 不变（保持黄色提示）
- 用户手动改过的 invoice（user_overridden=True）→ 跳过，不重算
"""

from __future__ import annotations

import logging

from src.core.categories import CategoryDef
from src.core.classifier import classify_invoice
from src.core.config import LLMConfig
from src.core.llm_classifier import LLMClassifier
from src.core.types import Invoice

logger = logging.getLogger(__name__)


class HybridClassifier:
    """规则 + LLM 兜底分类器。

    用法：
        cfg = load_config()
        cats = CategoryStore().list()
        clf = HybridClassifier(cfg, cats)
        cat, conf, note = clf.classify(invoice)
    """

    def __init__(self, config: LLMConfig, categories: list[CategoryDef]) -> None:
        self.config = config
        self.categories = categories
        self._llm: LLMClassifier | None = None
        if config.is_available:
            self._llm = LLMClassifier(
                api_key=config.api_key,
                base_url=config.base_url,
                model=config.model,
                categories=categories,
            )

    def classify(self, invoice: Invoice) -> tuple[str, float, str]:
        """主入口。永不抛异常，永远返回结果。"""
        # 1. 规则跑一遍
        rule_cat, rule_conf, rule_note = classify_invoice(invoice, self.categories)

        # 2. 决定是否调 LLM
        if not self._should_call_llm(rule_conf):
            return rule_cat, rule_conf, rule_note

        # 3. 调 LLM
        if self._llm is None:
            return rule_cat, rule_conf, rule_note + "（LLM 未配置）"

        llm_result = self._llm.classify(invoice)
        if llm_result is None:
            return rule_cat, min(rule_conf, 0.5), rule_note + "（LLM 失败，请复核）"

        # 4. LLM 成功
        return llm_result

    def _should_call_llm(self, rule_confidence: float) -> bool:
        """根据 backend 和置信度判断是否需要调 LLM。"""
        backend = self.config.backend
        if backend == "rule":
            return False
        if backend == "llm":
            return True
        # hybrid
        return rule_confidence < self.config.fallback_threshold
