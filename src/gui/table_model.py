"""发票表格的 QAbstractTableModel 实现。

列：文件名 | 类目 | 金额 | 发票号 | 销售方 | 日期 | 状态
- 类目列可编辑（QComboBox delegate）
- 状态列：✅ 已分类、⚠ 待复核、❌ 失败、✋ 手动归类
- 行底色根据状态变化（黄/红/绿/白）

类目值是字符串（类目名），不依赖枚举——支持用户自定义类目。
"""

from __future__ import annotations

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PyQt6.QtGui import QColor

from src.core.types import Invoice

COLUMNS = ["文件名", "类目", "金额", "发票号", "销售方", "日期", "状态"]


class InvoiceTableModel(QAbstractTableModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._invoices: list[Invoice] = []
        # 批量操作挂起 dataChanged，结束时一次性 emit（修原 #10：批量改类目频繁写盘）
        self._batching = False
        self._batch_dirty = False

    # --- 批量操作 ---
    def begin_batch(self) -> None:
        """开始批量操作。期间 dataChanged 被挂起。"""
        self._batching = True
        self._batch_dirty = False

    def end_batch(self) -> None:
        """结束批量操作。如有改动，一次性 emit dataChanged。"""
        if not self._batching:
            return
        self._batching = False
        if self._batch_dirty and self._invoices:
            self._batch_dirty = False
            ix = self.index(0, 0)
            ix2 = self.index(len(self._invoices) - 1, len(COLUMNS) - 1)
            self.dataChanged.emit(ix, ix2, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.BackgroundRole])

    def _emit_changed(self, row: int) -> None:
        """单行改动通知。批量模式下挂起。"""
        if self._batching:
            self._batch_dirty = True
            return
        ix = self.index(row, 0)
        ix2 = self.index(row, len(COLUMNS) - 1)
        self.dataChanged.emit(ix, ix2, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.BackgroundRole])

    # --- 数据接口 ---
    def set_invoices(self, invoices: list[Invoice]) -> None:
        self.beginResetModel()
        self._invoices = list(invoices)
        self.endResetModel()

    def add_invoice(self, inv: Invoice) -> None:
        row = len(self._invoices)
        self.beginInsertRows(QModelIndex(), row, row)
        self._invoices.append(inv)
        self.endInsertRows()

    def update_invoice(self, row: int, inv: Invoice) -> None:
        if 0 <= row < len(self._invoices):
            self._invoices[row] = inv
            self._emit_changed(row)

    def get_invoice(self, row: int) -> Invoice | None:
        if 0 <= row < len(self._invoices):
            return self._invoices[row]
        return None

    def all_invoices(self) -> list[Invoice]:
        return list(self._invoices)

    def clear(self) -> None:
        self.beginResetModel()
        self._invoices.clear()
        self.endResetModel()

    def remove_rows(self, row_indices: list[int]) -> int:
        """删除指定行的发票记录。返回实际删除的行数。

        会先按降序排序避免索引错位。
        """
        if not row_indices:
            return 0
        valid = sorted({i for i in row_indices if 0 <= i < len(self._invoices)}, reverse=True)
        if not valid:
            return 0
        for row in valid:
            self.beginRemoveRows(QModelIndex(), row, row)
            del self._invoices[row]
            self.endRemoveRows()
        return len(valid)

    def set_category_for_row(self, row: int, category_name: str) -> None:
        """用户在 UI 上改类目时调用。会标记 user_overridden。"""
        if 0 <= row < len(self._invoices):
            inv = self._invoices[row]
            inv.category = category_name
            inv.user_overridden = True
            inv.confidence = 1.0  # 用户改过视为最高置信度
            inv.note = "用户手动归类"
            self._emit_changed(row)

    def reassign_category(self, old_name: str, new_name: str) -> int:
        """类目改名/迁移时批量改类目。返回受影响行数。"""
        affected = 0
        self.begin_batch()
        try:
            for inv in self._invoices:
                if inv.category == old_name:
                    inv.category = new_name
                    affected += 1
                    self._batch_dirty = True
        finally:
            self.end_batch()
        return affected

    # --- QAbstractTableModel 必需方法 ---
    def rowCount(self, parent=QModelIndex()) -> int:  # type: ignore[override]
        return len(self._invoices)

    def columnCount(self, parent=QModelIndex()) -> int:  # type: ignore[override]
        return len(COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):  # type: ignore[override]
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal and 0 <= section < len(COLUMNS):
            return COLUMNS[section]
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):  # type: ignore[override]
        if not index.isValid():
            return None
        inv = self._invoices[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            return self._display_text(inv, col)

        if role == Qt.ItemDataRole.BackgroundRole:
            return QColor(self._row_color(inv))

        if role == Qt.ItemDataRole.ToolTipRole:
            return self._tooltip(inv, col)

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if col in (2,):  # 金额列右对齐
                return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

        return None

    def flags(self, index):  # type: ignore[override]
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        base = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        # 类目列（1）允许编辑（下拉框）
        if index.column() == 1:
            base |= Qt.ItemFlag.ItemIsEditable
        return base

    # --- 私有辅助 ---
    def _display_text(self, inv: Invoice, col: int) -> str:
        if col == 0:
            return inv.file_name
        if col == 1:
            return inv.category if inv.category else "—"
        if col == 2:
            if inv.amount is None:
                return "—"
            return f"¥ {inv.amount:,.2f}"
        if col == 3:
            return inv.invoice_no or "—"
        if col == 4:
            return inv.seller_name or "—"
        if col == 5:
            return inv.issue_date or "—"
        if col == 6:
            return self._status_text(inv)
        return ""

    def _status_text(self, inv: Invoice) -> str:
        if inv.error:
            return "❌ " + inv.error[:30]
        if inv.user_overridden:
            return "✋ 手动归类"
        if inv.confidence < 0.7:
            return "⚠ 待复核"
        return "✅"

    def _row_color(self, inv: Invoice) -> str:
        if inv.error:
            return "#ffcdd2"  # 红
        if inv.user_overridden:
            return "#c8e6c9"  # 绿
        if inv.confidence < 0.7:
            return "#fff9c4"  # 黄
        return "#ffffff"  # 白

    def _tooltip(self, inv: Invoice, col: int) -> str:
        if col == 6:
            parts = []
            if inv.note:
                parts.append(inv.note)
            if inv.error:
                parts.append(inv.error)
            return " | ".join(parts) if parts else ""
        return ""
