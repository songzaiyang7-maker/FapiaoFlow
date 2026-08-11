"""数据模型：发票数据类、Session（按日期分组的记录）。

类目（Category）改为字符串——具体类目定义见 src/core/categories.py，
用户可自由增删改。Invoice.category 存类目名（字符串），这样改名/删类目
不会让旧数据加载失败。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field


@dataclass
class Invoice:
    """单张发票的完整解析与分类结果。

    字段说明：
    - amount: 价税合计小写金额（报销口径），红字发票为负数
    - confidence: 分类置信度 0-1，低于 0.7 时界面黄色高亮提示用户复核
    - user_overridden: 用户手动改过类目（含拖到具体类目），后续自动重算应跳过
    - category: 类目名（字符串），具体定义见 categories.py
    - error: 非 None 表示解析失败（如未找到价税合计），此时 amount 为 None
    """

    file_path: str
    file_name: str
    raw_text: str = ""
    amount: float | None = None
    invoice_no: str | None = None
    issue_date: str | None = None
    seller_name: str | None = None
    category: str | None = None
    confidence: float = 0.0
    note: str | None = None
    error: str | None = None
    user_overridden: bool = False

    def needs_review(self) -> bool:
        """是否需要在 UI 上黄色高亮提示用户复核。"""
        if self.error:
            return False
        if self.user_overridden:
            return False
        return self.confidence < 0.7

    def to_dict(self) -> dict:
        """序列化为可 JSON 持久化的字典。"""
        return {
            "file_path": self.file_path,
            "file_name": self.file_name,
            "raw_text": self.raw_text,
            "amount": self.amount,
            "invoice_no": self.invoice_no,
            "issue_date": self.issue_date,
            "seller_name": self.seller_name,
            "category": self.category,
            "confidence": self.confidence,
            "note": self.note,
            "error": self.error,
            "user_overridden": self.user_overridden,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Invoice:
        # category 直接当字符串读——即使类目被改名/删除也不炸库（修原 #6）
        # category 值可能是历史遗留的任意字符串，UI 层负责兜底显示
        return cls(
            file_path=d.get("file_path", ""),
            file_name=d.get("file_name", ""),
            raw_text=d.get("raw_text", ""),
            amount=d.get("amount"),
            invoice_no=d.get("invoice_no"),
            issue_date=d.get("issue_date"),
            seller_name=d.get("seller_name"),
            category=d.get("category"),
            confidence=d.get("confidence", 0.0),
            note=d.get("note"),
            error=d.get("error"),
            user_overridden=d.get("user_overridden", False),
        )


@dataclass
class Session:
    """一次报销记录（按日期分组）。

    每次新建记录会创建一个 Session，包含若干发票。
    持久化到 data/sessions.json。
    """

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    date: str = ""              # YYYY-MM-DD，新建时自动填今天
    label: str = ""             # 用户可编辑的备注，如"出差北京"
    invoices: list[Invoice] = field(default_factory=list)

    def total_amount(self) -> float:
        return sum(i.amount or 0.0 for i in self.invoices)

    def invoice_count(self) -> int:
        return len(self.invoices)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "date": self.date,
            "label": self.label,
            "invoices": [inv.to_dict() for inv in self.invoices],
        }

    @classmethod
    def from_dict(cls, d: dict) -> Session:
        return cls(
            id=d.get("id") or uuid.uuid4().hex[:12],
            date=d.get("date", ""),
            label=d.get("label", ""),
            invoices=[Invoice.from_dict(i) for i in d.get("invoices", [])],
        )
