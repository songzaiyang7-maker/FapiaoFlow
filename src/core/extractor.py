"""从电子发票文本中提取结构化字段。

提取目标：
- amount: 价税合计小写（委托 utils/amount.py）
- invoice_no: 发票号码（8-20 位数字）
- issue_date: 开票日期（YYYY-MM-DD）
- seller_name: 销售方名称

电子发票的文本布局因开票方/格式而异，主要有三类（来自真实发票样本）：

1. 标准竖排布局：
        销售方名称: 杭州XX酒店管理有限公司
        发票号码: 24400000000000000000
        开票日期: 2026年08月10日

2. 购销方左右并列布局（打车/网约车发票常见）：
        购 名称：浙江大学 销 名称：苏州市吉利优行电子科技有限公司
        买 售
        方 方

3. 字段分散/跨行布局（部分酒店发票）：
        发票号码：
        ...
        制 26112000003231988456
        国家税务总局 2026年08月04日
        ...
        浙江大学 北京华邮国鼎酒店管理有限公司

字段不一定全部出现，缺失返回 None。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.utils.amount import extract_amount

# 发票号码：
# - 标准：发票号码: 24400000000000000000（20 位，紧跟冒号后）
# - 跨行：发票号码：\n...\n26112000003231988456（冒号后空白/换行，数字在后面）
# - 老式：8-10 位
# 注意：发票代码是单独的数字串，发票号码通常 ≥ 8 位且与代码不同
_INVOICE_NO_PATTERNS = [
    # 标准：发票号码 后紧跟冒号和数字（允许冒号后换行再出现数字）
    re.compile(r"发票号码\s*[：:号]*\s*(\d{8,20})"),
    # 跨行：发票号码：\s*(后面任意字符内出现 18-20 位数字)
    re.compile(r"发票号码\s*[：:]\s*.*?(\d{18,20})", re.DOTALL),
    re.compile(r"票据号码\s*[：:]*\s*(\d{8,20})"),
]

# 开票日期：统一允许 中英文冒号 + 可选空格
# 匹配 "2026年08月10日" / "2026-08-10" / "2026/8/10"
# 支持冒号后跨行（部分发票"开票日期："后日期在下一区域）
_DATE_PATTERNS = [
    # 标准：开票日期: 2026年08月10日（同行）
    re.compile(r"开票日期\s*[：:]\s*(\d{4}[年/-]\d{1,2}[月/-]\d{1,2}日?)"),
    re.compile(r"开票日期\s*[：:]?\s+(\d{4}[-/]\d{1,2}[-/]\d{1,2})"),
    # 跨行：开票日期：\s*(后面任意字符内出现中文日期)
    re.compile(r"开票日期\s*[：:]\s*.*?(\d{4}年\d{1,2}月\d{1,2}日)", re.DOTALL),
]

# 销售方名称：按精确度从高到低尝试，避免误匹配购买方
# 关键：真实发票里"购 名称：A 销 名称：B"在同一行，宽松的"名称:"会先撞到购买方
_SELLER_PATTERNS = [
    # 最精确：销售方名称: xxx 或 销售方名称：xxx
    re.compile(r"销售方名称\s*[：:]\s*(.+?)\s*$", re.MULTILINE),
    # 左右并列布局：销 名称：xxx 或 售 名称：xxx（"销/售"字前缀，冒号后紧跟内容）
    # 用 \S 限制冒号后必须有非空白字符（避免匹配"售 名称："后空白的情况）
    re.compile(r"[销售]\s*名称\s*[：:]\s*(\S.*?)\s*$", re.MULTILINE),
    # 兜底：单纯 名称: xxx（最后才用，且调用方需过滤掉明显是购买方的）
    re.compile(r"^\s*名称\s*[：:]\s*(.+?)\s*$", re.MULTILINE),
]

# 已知的购买方标识（用于过滤误匹配）：如果提取出的名字像购买方则丢弃
# 购买方常见特征：教育机构、政府机关（销售方一般是公司/企业）
_BUYER_HINTS = ["大学", "学院", "学校", "局", "委", "办", "院"]
# 销售方标识（公司/企业特征）
_SELLER_HINTS = ["公司", "酒店", "宾馆", "商店", "有限", "合伙", "事务所", "集团", "中心", "工作室"]


def _is_likely_buyer(name: str) -> bool:
    """粗略判断一个名字是否更像购买方而非销售方。

    真实样本里购买方多为"XX大学""XX局"，销售方多为"XX科技有限公司""XX酒店"。
    这是启发式，会漏判但宁可漏判（返回 False 走兜底）也不要错杀。
    """
    if not name:
        return False
    has_buyer_hint = any(h in name for h in _BUYER_HINTS)
    has_seller_hint = any(h in name for h in _SELLER_HINTS)
    # 只有购买方特征、无销售方特征时判定为购买方
    return has_buyer_hint and not has_seller_hint


def _extract_company_entities(text: str) -> list[str]:
    """从全文里抽取"像销售方公司名"的实体，作为最后兜底。

    针对极端分散布局：发票号/日期/销售方名称都不在标签后，
    只能靠"含公司特征词"的实体来识别销售方。
    """
    entities: list[str] = []
    # 匹配"XX有限公司""XX酒店"等，名字可能含中文/字母/括号
    # 用 findall 找所有候选，再过滤购买方
    pattern = re.compile(r"([\u4e00-\u9fa5A-Za-z0-9（）()]+(?:有限公司|股份公司|酒店|宾馆|商店|合伙企业|事务所|集团))")
    for m in pattern.finditer(text):
        name = m.group(1).strip()
        # 太短的丢弃（如单独"集团"二字）
        if len(name) < 4:
            continue
        if not _is_likely_buyer(name):
            entities.append(name)
    return entities


def _normalize_date(raw: str) -> str:
    """'2026年08月10日' / '2026/8/10' → '2026-08-10'。"""
    s = raw.replace("年", "-").replace("月", "-").replace("日", "")
    s = s.replace("/", "-")
    parts = [p for p in s.split("-") if p]
    if len(parts) != 3:
        return raw.strip()
    y, m, d = parts
    try:
        return f"{y}-{int(m):02d}-{int(d):02d}"
    except ValueError:
        return raw.strip()


@dataclass
class ExtractedFields:
    amount: float | None
    invoice_no: str | None
    issue_date: str | None
    seller_name: str | None


def _extract_invoice_no(text: str) -> str | None:
    """提取发票号。跨行 pattern 用 findall 取最后一个（避免误匹配发票代码）。"""
    for pat in _INVOICE_NO_PATTERNS:
        matches = list(pat.finditer(text))
        if matches:
            # 多个匹配时取最后一个（发票号码通常在发票代码之后）
            return matches[-1].group(1).strip()
    return None


def _extract_seller(text: str) -> str | None:
    """提取销售方名称，过滤误匹配的购买方。

    策略：
    1. 按精确正则尝试（销售方名称:/销 名称:/...）
    2. 全部失败时，从全文找"像公司名"的实体兜底
    """
    for pat in _SELLER_PATTERNS:
        for m in pat.finditer(text):
            raw = m.group(1).rstrip("\r\n").strip()
            if not raw:
                continue
            # 取第一行（防止跨行匹配连带后续内容）
            candidate = raw.splitlines()[0].strip()
            # 过滤：名字里若含"名称:"字样，说明匹配多了（如"浙江大学 销 名称：苏州..."）
            # 取最后一个"名称"之后的部分
            if "名称" in candidate:
                idx = candidate.rfind("名称")
                after = candidate[idx + 2:].lstrip("：: \t")
                if after and not _is_likely_buyer(after):
                    return after
                continue
            # 过滤：如果名字像购买方（大学/局等）且无销售方特征，跳过继续找
            if _is_likely_buyer(candidate):
                continue
            # 过滤：纯方位字或空白（"方 方"、"方" 这种误匹配）
            cleaned = candidate.replace("方", "").replace(" ", "").strip()
            if cleaned == "" or len(candidate.strip()) < 2:
                continue
            return candidate
    # 全部正则失败 → 兜底：从全文找像销售方公司的实体
    entities = _extract_company_entities(text)
    return entities[0] if entities else None


def extract_fields(text: str) -> ExtractedFields:
    """从发票全文中提取所有结构化字段。"""
    if not text:
        return ExtractedFields(amount=None, invoice_no=None, issue_date=None, seller_name=None)

    amount = extract_amount(text)
    invoice_no = _extract_invoice_no(text)

    issue_date: str | None = None
    for pat in _DATE_PATTERNS:
        m = pat.search(text)
        if m:
            issue_date = _normalize_date(m.group(1))
            break

    seller_name = _extract_seller(text)

    return ExtractedFields(
        amount=amount,
        invoice_no=invoice_no,
        issue_date=issue_date,
        seller_name=seller_name,
    )
