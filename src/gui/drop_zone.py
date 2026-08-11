"""拖拽接收区组件。

支持：
- 多文件拖入
- 文件夹拖入（递归扫描 PDF）
- 单击打开文件选择对话框
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFileDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout


class DropZone(QFrame):
    """拖拽区。发射 paths_selected 信号，传 list[str] 给主窗口。"""

    paths_selected = pyqtSignal(list)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("DropZone")
        self.setAcceptDrops(True)
        self.setMinimumHeight(140)
        self.setFrameShape(QFrame.Shape.StyledPanel)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.hint = QLabel("📥  拖入发票 PDF（支持多选 / 文件夹）")
        self.hint.setObjectName("DropZoneHint")
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.sub = QLabel("或")
        self.sub.setObjectName("DropZoneSub")
        self.sub.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.button = QPushButton("选择文件")
        self.button.setObjectName("SecondaryButton")
        self.button.clicked.connect(self._open_file_dialog)

        h = QHBoxLayout()
        h.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h.addWidget(self.button)

        layout.addWidget(self.hint)
        layout.addWidget(self.sub)
        layout.addLayout(h)

    # --- 拖拽事件 ---
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
                # 递归扫描 PDF
                pdfs = sorted(p.rglob("*.pdf"))
                paths.extend(str(x) for x in pdfs)
            elif p.is_file() and p.suffix.lower() == ".pdf":
                paths.append(str(p))
        if paths:
            self.paths_selected.emit(paths)

    # --- 文件选择对话框 ---
    def _open_file_dialog(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "选择发票 PDF",
            "",
            "PDF 文件 (*.pdf)",
        )
        if files:
            self.paths_selected.emit(files)
