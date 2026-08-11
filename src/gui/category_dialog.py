"""类目管理对话框：增/删/改名/改关键词/改颜色。

通过"设置 → 类目管理"打开。
确认后写回 categories.json 并发 categories_changed 信号，主窗口据此刷新所有依赖组件。

删除类目时，若当前 session 有该类发票，会提示用户选迁移目标。
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.core.categories import CategoryDef

# 预设配色板（柔和卡片色）
_COLOR_PALETTE = [
    "#e3f2fd",  # 蓝
    "#fff3e0",  # 橙
    "#e8f5e9",  # 绿
    "#f3e5f5",  # 紫
    "#fce4ec",  # 粉
    "#fffde7",  # 黄
    "#e0f7fa",  # 青
    "#efebe9",  # 棕
]


class CategoryEditPanel(QWidget):
    """右侧编辑面板：编辑当前选中类目的属性。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._current: CategoryDef | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QFormLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("类目名（如：差旅）")
        layout.addRow("类目名：", self.name_edit)

        self.priority_edit = QLineEdit()
        self.priority_edit.setPlaceholderText("数字（越小越优先）")
        layout.addRow("优先级：", self.priority_edit)

        # 关键词：每行一个
        self.keywords_edit = QTextEdit()
        self.keywords_edit.setPlaceholderText("每行一个关键词，如：\n航空\n机票\n酒店")
        self.keywords_edit.setMaximumHeight(160)
        layout.addRow("关键词：", self.keywords_edit)

        # 颜色
        color_row = QHBoxLayout()
        self.color_preview = QLabel()
        self.color_preview.setFixedSize(40, 24)
        self.color_preview.setText("　")
        self.color_btn = QPushButton("选颜色…")
        self.color_btn.clicked.connect(self._pick_color)
        color_row.addWidget(self.color_preview)
        color_row.addWidget(self.color_btn)
        color_row.addStretch()
        color_widget = QWidget()
        color_widget.setLayout(color_row)
        layout.addRow("按钮颜色：", color_widget)

        self._current_color = "#e3f2fd"
        self._update_color_preview()

        # 输入变化时回写到 _current
        self.name_edit.textChanged.connect(self._on_field_changed)
        self.priority_edit.textChanged.connect(self._on_field_changed)
        self.keywords_edit.textChanged.connect(self._on_field_changed)

    def _pick_color(self) -> None:
        color = QColorDialog.getColor(QColor(self._current_color), self, "选择类目颜色")
        if color.isValid():
            self._current_color = color.name()
            self._update_color_preview()
            # 颜色变化也回写
            if self._current:
                self._current.color = self._current_color

    def _update_color_preview(self) -> None:
        self.color_preview.setStyleSheet(
            f"background-color: {self._current_color}; border: 1px solid #ccc; border-radius: 3px;"
        )

    def load(self, cat: CategoryDef) -> None:
        """加载一个类目到编辑面板。"""
        self._current = cat
        # 临时断开信号，避免 setText 触发 _on_field_changed 死循环
        self.name_edit.blockSignals(True)
        self.priority_edit.blockSignals(True)
        self.keywords_edit.blockSignals(True)
        self.name_edit.setText(cat.name)
        self.priority_edit.setText(str(cat.priority))
        self.keywords_edit.setPlainText("\n".join(cat.keywords))
        self.name_edit.blockSignals(False)
        self.priority_edit.blockSignals(False)
        self.keywords_edit.blockSignals(False)
        self._current_color = cat.color
        self._update_color_preview()

    def clear(self) -> None:
        self._current = None
        self.name_edit.blockSignals(True)
        self.priority_edit.blockSignals(True)
        self.keywords_edit.blockSignals(True)
        self.name_edit.clear()
        self.priority_edit.clear()
        self.keywords_edit.clear()
        self.name_edit.blockSignals(False)
        self.priority_edit.blockSignals(False)
        self.keywords_edit.blockSignals(False)

    def _on_field_changed(self) -> None:
        """编辑面板字段变化时回写到当前类目对象。"""
        if self._current is None:
            return
        self._current.name = self.name_edit.text().strip()
        try:
            self._current.priority = int(self.priority_edit.text().strip())
        except ValueError:
            pass  # 非法输入暂不写，保存时会校验
        # 关键词按行切分，去空行去空白
        text = self.keywords_edit.toPlainText()
        self._current.keywords = [
            line.strip() for line in text.splitlines() if line.strip()
        ]
        self._current.color = self._current_color


class CategoryManagerDialog(QDialog):
    """类目管理对话框。

    用法：
        dlg = CategoryManagerDialog(categories, invoice_count_by_cat, parent)
        if dlg.exec() == QDialog.Accepted:
            new_cats = dlg.result_categories()
    """

    def __init__(
        self,
        categories: list[CategoryDef],
        invoice_count_by_category: dict[str, int] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("类目管理")
        self.resize(720, 480)
        self._categories = [CategoryDef(
            name=c.name, keywords=list(c.keywords), color=c.color, priority=c.priority
        ) for c in categories]
        self._invoice_counts = invoice_count_by_category or {}
        self._migration: tuple[str, str] | None = None
        self._build_ui()
        self._refresh_list()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)

        # 中部：左右两栏
        middle = QHBoxLayout()

        # 左侧：类目列表 + 增删按钮
        left = QVBoxLayout()
        left.addWidget(QLabel("类目列表"))
        self.list_widget = QListWidget()
        self.list_widget.currentItemChanged.connect(self._on_select)
        left.addWidget(self.list_widget, stretch=1)

        btn_row = QHBoxLayout()
        self.add_btn = QPushButton("+ 新增")
        self.add_btn.clicked.connect(self._on_add)
        self.del_btn = QPushButton("删除")
        self.del_btn.clicked.connect(self._on_delete)
        btn_row.addWidget(self.add_btn)
        btn_row.addWidget(self.del_btn)
        btn_row.addStretch()
        left.addLayout(btn_row)

        left_widget = QWidget()
        left_widget.setLayout(left)
        left_widget.setFixedWidth(220)
        middle.addWidget(left_widget)

        # 右侧：编辑面板
        self.edit_panel = CategoryEditPanel()
        middle.addWidget(self.edit_panel, stretch=1)

        outer.addLayout(middle, stretch=1)

        # 底部按钮
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    def _on_select(self, current, previous) -> None:
        if current is None:
            self.edit_panel.clear()
            return
        idx = current.data(Qt.ItemDataRole.UserRole)
        if idx is not None and 0 <= idx < len(self._categories):
            self.edit_panel.load(self._categories[idx])

    def _refresh_list(self) -> None:
        """刷新左侧列表（保持当前选中）。"""
        selected_idx = -1
        if self.list_widget.currentItem():
            selected_idx = self.list_widget.currentItem().data(Qt.ItemDataRole.UserRole)

        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        # 按 priority 升序显示
        indexed = sorted(enumerate(self._categories), key=lambda x: (x[1].priority, x[1].name))
        for orig_idx, cat in indexed:
            count = self._invoice_counts.get(cat.name, 0)
            label = f"{cat.name}" + (f"  ({count} 张)" if count > 0 else "")
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, orig_idx)
            self.list_widget.addItem(item)
            if orig_idx == selected_idx:
                self.list_widget.setCurrentItem(item)
        self.list_widget.blockSignals(False)

        # 若没选中项，默认选第一个
        if self.list_widget.currentItem() is None and self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    def _on_add(self) -> None:
        """新增类目。"""
        # 先提交当前编辑面板的改动到 _categories（load 时已绑定引用，无需额外保存）
        new_cat = CategoryDef(
            name="新类目",
            keywords=[],
            color=_COLOR_PALETTE[len(self._categories) % len(_COLOR_PALETTE)],
            priority=(max((c.priority for c in self._categories), default=0) + 1),
        )
        self._categories.append(new_cat)
        self._refresh_list()
        # 选中新加的
        for i in range(self.list_widget.count()):
            if self.list_widget.item(i).data(Qt.ItemDataRole.UserRole) == len(self._categories) - 1:
                self.list_widget.setCurrentRow(i)
                break
        self.edit_panel.name_edit.setFocus()
        self.edit_panel.name_edit.selectAll()

    def _on_delete(self) -> None:
        """删除当前选中类目。若有发票属于该类，提示选迁移目标。"""
        if self.list_widget.currentItem() is None:
            return
        idx = self.list_widget.currentItem().data(Qt.ItemDataRole.UserRole)
        if idx is None or not (0 <= idx < len(self._categories)):
            return
        cat = self._categories[idx]
        count = self._invoice_counts.get(cat.name, 0)

        if len(self._categories) <= 1:
            QMessageBox.warning(self, "无法删除", "至少保留一个类目。")
            return

        if count > 0:
            # 提示选迁移目标
            other_names = [c.name for c in self._categories if c.name != cat.name]
            target, ok = QInputDialog.getItem(
                self,
                "迁移发票",
                f"当前有 {count} 张发票属于「{cat.name}」。\n请选择这些发票迁移到哪个类目：",
                other_names,
                0,
                False,
            )
            if not ok:
                return
            # 记录迁移意图（主窗口在 result_categories 后处理）
            self._migration = (cat.name, target)

        self._categories.pop(idx)
        self._refresh_list()
        self.edit_panel.clear()

    def _on_accept(self) -> None:
        """确定：校验后接受。"""
        # 同步编辑面板当前改动（load 已绑定引用，字段变化已回写，这里只做校验）
        names = [c.name.strip() for c in self._categories]
        # 校验：不能为空
        for c in self._categories:
            if not c.name.strip():
                QMessageBox.warning(self, "类目名无效", "所有类目必须有名称。")
                return
        # 校验：不能重名
        if len(set(names)) != len(names):
            QMessageBox.warning(self, "类目名重复", "类目名不能重复。")
            return
        # 校验：优先级是整数（非法时给默认值）
        for c in self._categories:
            try:
                c.priority = int(c.priority)
            except (ValueError, TypeError):
                c.priority = 99
        self.accept()

    def result_categories(self) -> list[CategoryDef]:
        """返回编辑后的类目列表（已按 priority 升序）。"""
        return sorted(self._categories, key=lambda c: (c.priority, c.name))

    @property
    def migration(self) -> tuple[str, str] | None:
        """返回 (被删类目名, 迁移目标类目名)，无删除则 None。"""
        return self._migration
