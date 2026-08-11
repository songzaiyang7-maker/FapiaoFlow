"""金额提取：从电子发票文本中解析"价税合计"小写金额。

电子发票（增值税电子普通发票）的标准格式：
    价税合计（大写） Ⓐ 圆整  （小写） ￥1234.56

我们只要小写金额（即报销口径），不要中文大写。
红字发票（冲红/退款）金额是负数，如 ￥-14.38，也需要正确解析。

正则策略三层兜底：
1. 优先匹配"价税合计 ... ￥XXX.XX"（允许前导负号，处理红字发票）
2. 退而求其次匹配"（小写） ￥XXX.XX"
3. 最后兜底：文末最后一个 ￥ 后的金额（仅对正数发票可靠，红字发票不在此兜底）
"""

from __future__ import annotations

import re

# 全角/半角 ￥，允许前后空白与千分位逗号；支持前导负号（红字发票）
# 兜底用：扫描所有 ￥ 金额
_AMOUNT_PATTERN = re.compile(
    r"[¥￥]\s*([-]?[0-9][0-9,]*\.?[0-9]{0,2})"
)

# "价税合计"行整体匹配（贪婪到第一个 ￥），要求小数点后两位（标准格式）
# 允许前导负号——红字发票"价税合计"为负
_JIA_SHUI_HE_JI = re.compile(
    r"价税合计[^\n]*?[¥￥]\s*([-]?[0-9][0-9,]*\.[0-9]{2})",
    re.DOTALL,
)

# "（小写）" 标记后第一个金额，允许前导负号
_XIAO_XIE = re.compile(
    r"[（(]\s*小写\s*[）)]\s*[¥￥]?\s*([-]?[0-9][0-9,]*\.[0-9]{2})"
)


def _to_float(raw: str) -> float:
    """'1,234.56' / '-14.38' → 1234.56 / -14.38。"""
    return float(raw.replace(",", "").strip())


def extract_amount(text: str) -> float | None:
    """从发票全文中提取价税合计小写金额。

    返回 None 表示未匹配到。调用方可据此标记解析失败。

    红字发票返回负数。
    """
    if not text:
        return None

    # 第一优先级：价税合计行（支持负数）
    m = _JIA_SHUI_HE_JI.search(text)
    if m:
        try:
            return _to_float(m.group(1))
        except ValueError:
            pass

    # 第二优先级：（小写）标记（支持负数）
    m = _XIAO_XIE.search(text)
    if m:
        try:
            return _to_float(m.group(1))
        except ValueError:
            pass

    # 兜底：扫描所有 ￥ 金额
    # 注意：红字发票的兜底不可靠——发票里可能有正数税额行，max 会取错。
    # 因此兜底只采纳正数；若所有候选都是负数（纯红字发票），返回 None（让上层标记待人工）。
    candidates: list[float] = []
    has_negative = False
    for m in _AMOUNT_PATTERN.finditer(text):
        try:
            v = _to_float(m.group(1))
        except ValueError:
            continue
        if v < 0:
            has_negative = True
        else:
            candidates.append(v)
    if candidates:
        return max(candidates)

    # 所有候选都是负数（纯红字发票且无价税合计行标签）——无法可靠判定，返回 None
    # 上层会标记"未找到价税合计"，用户需人工处理
    if has_negative:
        return None

    return None
