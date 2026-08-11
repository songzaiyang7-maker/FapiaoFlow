"""类目列的下拉框 delegate。

双击类目单元格 → 弹出 QComboBox → 选择新类目 → 标记 user_overridden=True

类目列表从构造参数传入（支持用户自定义类目）。
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QComboBox, QStyledItemDelegate


class CategoryDelegate(QStyledItemDelegate):
    """类目列的 ComboBox 编辑器。"""

    def __init__(self, category_names: list[str], parent=None) -> None:
        super().__init__(parent)
        self._category_names = list(category_names)

    def set_categories(self, category_names: list[str]) -> None:
        """类目配置变更后刷新下拉项。"""
        self._category_names = list(category_names)

    def createEditor(self, parent, option, index):  # type: ignore[override]
        combo = QComboBox(parent)
        for name in self._category_names:
            combo.addItem(name, userData=name)
        return combo

    def setEditorData(self, editor, index):  # type: ignore[override]
        combo: QComboBox = editor
        current_text = index.data(Qt.ItemDataRole.DisplayRole)
        # 找到当前值的 index
        for i in range(combo.count()):
            if combo.itemText(i) == current_text:
                combo.setCurrentIndex(i)
                return
        # 当前值不在类目列表（如类目被删后的遗留发票）→ 追加显示
        if current_text and current_text != "—":
            combo.addItem(current_text, userData=current_text)
            combo.setCurrentIndex(combo.count() - 1)
        else:
            combo.setCurrentIndex(0)

    def setModelData(self, editor, model, index):  # type: ignore[override]
        combo: QComboBox = editor
        new_category: str = combo.currentData()
        # 通过 model 的专用方法写入，会同步更新 Invoice 对象
        if hasattr(model, "set_category_for_row"):
            model.set_category_for_row(index.row(), new_category)
        else:
            model.setData(index, new_category, Qt.ItemDataRole.EditRole)
