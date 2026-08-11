"""拖到具体类目的按钮组件。

每个按钮代表一个类目。
拖入文件到按钮 → 强制归该类，跳过自动分类。

按钮列表从构造参数传入（支持用户自定义类目）。
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout


class CategoryDropButton(QFrame):
    """单个类目拖拽目标按钮。

    信号 paths_dropped(list[str], str)：路径列表 + 类目名
    """

    paths_dropped = pyqtSignal(list, str)

    def __init__(self, category_name: str, color: str, parent=None) -> None:
        super().__init__(parent)
        self.category_name = category_name
        self.setAcceptDrops(True)
        self.setMinimumHeight(64)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("CategoryDropButton")
        self.setStyleSheet(f"""
            QFrame#CategoryDropButton {{
                background-color: {color};
                border-radius: 8px;
                border: 1.5px dashed #b0b8c8;
            }}
            QFrame#CategoryDropButton:hover {{
                background-color: {color};
                border: 2px dashed #4a6fff;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(2)
        # 上行：类目名
        lbl = QLabel(category_name)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("font-size: 14px; font-weight: 600; color: #2c2c2c; border: none;")
        layout.addWidget(lbl)
        # 下行：拖入提示
        hint = QLabel("📥 拖入到此")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet("font-size: 11px; color: #888; border: none;")
        layout.addWidget(hint)

    def dragEnterEvent(self, event) -> None:  # type: ignore[override]
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:  # type: ignore[override]
        urls = event.mimeData().urls()
        paths: list[str] = []
        for url in urls:
            local = url.toLocalFile()
            if not local:
                continue
            p = Path(local)
            if p.is_dir():
                # 大小写不敏感匹配 .pdf / .PDF
                pdfs = sorted([x for x in p.rglob("*") if x.suffix.lower() == ".pdf"])
                paths.extend(str(x) for x in pdfs)
            elif p.is_file() and p.suffix.lower() == ".pdf":
                paths.append(str(p))
        if paths:
            self.paths_dropped.emit(paths, self.category_name)


class CategoryDropBar(QFrame):
    """类目按钮一排（按钮从配置动态生成）。"""

    paths_dropped = pyqtSignal(list, str)  # (paths, category_name)

    def __init__(self, categories: list, parent=None) -> None:
        """categories: list[CategoryDef]，按 priority 升序。"""
        super().__init__(parent)
        self._categories = categories
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self._buttons: list[CategoryDropButton] = []
        self._rebuild_buttons()

    def _rebuild_buttons(self) -> None:
        """根据当前类目重建按钮。"""
        # 清除旧按钮
        for btn in self._buttons:
            btn.setParent(None)
            btn.deleteLater()
        self._buttons.clear()
        for cat in self._categories:
            btn = CategoryDropButton(cat.name, cat.color)
            btn.paths_dropped.connect(self.paths_dropped.emit)
            self.layout().addWidget(btn)
            self._buttons.append(btn)

    def update_categories(self, categories: list) -> None:
        """类目配置变更后刷新按钮。"""
        self._categories = categories
        self._rebuild_buttons()
