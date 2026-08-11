"""基于 DeepSeek API 的发票分类器。

设计：
- 把发票文本（销售方+金额+部分原文）+ 当前类目列表发给 LLM
- 让 LLM 返回 JSON：{"category": "...", "reason": "..."}
- 解析失败、网络错误、API key 缺失 → 返回 None，让 HybridClassifier 兜底

类目列表动态注入 prompt，支持用户自定义类目。
"""

from __future__ import annotations

import json
import logging

from openai import OpenAI

from src.core.categories import CategoryDef
from src.core.types import Invoice

logger = logging.getLogger(__name__)


def build_system_prompt(categories: list[CategoryDef]) -> str:
    """根据当前类目列表动态生成 system prompt。"""
    sorted_cats = sorted(categories, key=lambda c: (c.priority, c.name))
    cat_lines = []
    for c in sorted_cats:
        kw = "、".join(c.keywords[:10]) if c.keywords else "（无关键词，兜底类目）"
        cat_lines.append(f"- {c.name}：关键词示例（{kw}）")
    cat_block = "\n".join(cat_lines)
    cat_names = "、".join(c.name for c in sorted_cats)

    return f"""你是发票分类助手，帮用户把发票分到以下类目之一：

{cat_block}

分类规则：
1. 优先按销售方名称和货物名称里的关键词匹配上述类目
2. 跨城交通（高铁/火车/机票/航班/客运）和住宿（酒店/宾馆/民宿）一般归"差旅"类（如果存在）
3. 本地打车/网约车/公交/地铁归本地交通类（如果存在），但销售方不含城市信息时无法确定是否本地——默认归此类即可
4. 多个类目都匹配时，按关键词命中数和语义相关性选择最贴切的
5. 实在无法判断 → 归兜底类目（priority 最大的那个）

只返回 JSON，category 必须是以下之一：{cat_names}
{{"category": "...", "reason": "30字以内的判断依据"}}
"""


# 默认兜底类目名（prompt 里"实在无法判断"时用）
_FALLBACK_SENTINEL = "__FALLBACK__"


class LLMClassifier:
    """调用 DeepSeek API 进行分类。

    异常处理策略：
    - API key 缺失、网络错误、JSON 解析失败、返回无效类目 → 返回 None
    - 调用方应处理 None（回退到规则结果）

    categories 用于：动态生成 prompt、校验 LLM 返回的类目名合法。
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        categories: list[CategoryDef],
        timeout: float = 30.0,
    ) -> None:
        self.client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)
        self.model = model
        self.categories = categories
        self._system_prompt = build_system_prompt(categories)
        # 合法类目名集合 + 兜底类目（priority 最大的）
        self._valid_names = {c.name for c in categories}
        sorted_cats = sorted(categories, key=lambda c: (c.priority, c.name), reverse=True)
        self._fallback_name = sorted_cats[0].name if sorted_cats else None

    def classify(self, invoice: Invoice) -> tuple[str, float, str] | None:
        """返回 (category_name, confidence, note) 或 None（失败时）。"""
        user_msg = self._build_user_message(invoice)
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._system_prompt},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.0,            # 分类任务用 0 温度保证稳定
                max_tokens=200,
                response_format={"type": "json_object"},
            )
        except Exception as e:
            logger.warning(f"DeepSeek API 调用失败 {invoice.file_name}: {e}")
            return None

        content = resp.choices[0].message.content or ""
        return self._parse_response(content)

    def _build_user_message(self, invoice: Invoice) -> str:
        """构造发给 LLM 的用户消息，截断 raw_text 控制成本。"""
        # 取 raw_text 前 1500 字（够 LLM 判断，又不会太贵）
        truncated_text = (invoice.raw_text or "")[:1500]
        parts = [
            f"销售方名称：{invoice.seller_name or '未知'}",
            f"金额：{invoice.amount if invoice.amount is not None else '未知'}",
            f"开票日期：{invoice.issue_date or '未知'}",
            "发票文本（可能截断）：",
            truncated_text,
        ]
        return "\n".join(parts)

    def _parse_response(self, content: str) -> tuple[str, float, str] | None:
        """解析 LLM 返回的 JSON。"""
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            logger.warning(f"LLM 返回非 JSON: {content[:200]}")
            return None

        cat_str = str(data.get("category", "")).strip()
        reason = str(data.get("reason", "")).strip()

        if cat_str not in self._valid_names:
            logger.warning(f"LLM 返回无效类目: {cat_str}")
            return None

        note = f"LLM 判定：{reason}" if reason else "LLM 判定"
        return cat_str, 0.95, note
