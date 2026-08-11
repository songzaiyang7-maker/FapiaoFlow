"""左侧 Session 导航面板。

显示按日期分组的所有 session，支持切换/新建/删除。
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)


class SessionPanel(QFrame):
    """左侧记录导航栏。

    信号：
    - session_selected(str): 切换到某个 session（id）
    - new_session_requested(): 点击"新建记录"
    - delete_session_requested(str): 右键删除某个 session
    """

    session_selected = pyqtSignal(str)
    new_session_requested = pyqtSignal()
    delete_session_requested = pyqtSignal(str)
    rename_requested = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("SessionPanel")
        self.setFixedWidth(200)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 12, 8, 12)
        layout.setSpacing(8)

        title = QLabel("📅 记录")
        title.setObjectName("PanelTitle")
        layout.addWidget(title)

        self.list_widget = QListWidget()
        self.list_widget.setObjectName("SessionList")
        self.list_widget.setFrameShape(QFrame.Shape.NoFrame)
        self.list_widget.setSpacing(2)
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._on_context_menu)
        self.list_widget.currentItemChanged.connect(self._on_current_changed)
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.list_widget, stretch=1)

        self.new_btn = QPushButton("+ 新建记录")
        self.new_btn.setObjectName("PrimaryButton")
        self.new_btn.clicked.connect(self.new_session_requested.emit)
        layout.addWidget(self.new_btn)

    def refresh(self, sessions: list, current_id: str | None = None) -> None:
        """重渲染列表。sessions 是 Session 对象列表（已按日期降序）。"""
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        select_row = -1
        for i, s in enumerate(sessions):
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, s.id)
            item.setText(self._format_label(s))
            if s.id == current_id:
                select_row = i
            self.list_widget.addItem(item)
        if select_row >= 0:
            self.list_widget.setCurrentRow(select_row)
        self.list_widget.blockSignals(False)

    def _format_label(self, session) -> str:
        """生成 session 在列表里显示的文本。

        格式：
            08-10  出差北京
             5 张  ¥1,675
        """
        # 只取月-日（年份默认当年）
        date_short = session.date[5:] if len(session.date) >= 10 else session.date
        line1 = date_short
        if session.label:
            line1 += f"  {session.label}"
        n = session.invoice_count()
        amt = session.total_amount()
        return f"{line1}\n{n} 张  ¥{amt:,.0f}"

    def _on_current_changed(self, current, previous) -> None:
        if current is None:
            return
        sid = current.data(Qt.ItemDataRole.UserRole)
        if sid:
            self.session_selected.emit(sid)

    def _on_context_menu(self, pos) -> None:
        from PyQt6.QtWidgets import QMenu

        item = self.list_widget.itemAt(pos)
        if item is None:
            return
        sid = item.data(Qt.ItemDataRole.UserRole)
        menu = QMenu(self)
        act_rename = menu.addAction("编辑备注")
        menu.addSeparator()
        act_delete = menu.addAction("删除此记录")
        chosen = menu.exec(self.list_widget.mapToGlobal(pos))
        if chosen is act_rename:
            self.rename_requested.emit(sid)
        elif chosen is act_delete:
            self.delete_session_requested.emit(sid)

    def _on_item_double_clicked(self, item) -> None:
        sid = item.data(Qt.ItemDataRole.UserRole)
        if sid:
            self.rename_requested.emit(sid)
