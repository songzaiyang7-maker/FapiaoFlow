"""拖拽区容器：左右两栏布局。

左侧：自动分类拖拽区（大，醒目）—— 拖到这里由程序智能判断类目
右侧：指定类目拖拽区（多个卡片）—— 拖到某个类目卡片强制归该类

设计意图：让用户一眼看到"有两种拖法"，而不是只注意到上面那个大框。
"""

from __future__ import annotations

from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from src.gui.category_drop import CategoryDropBar
from src.gui.drop_zone import DropZone


class DropArea(QWidget):
    """拖拽区容器：左右两栏并列。

    左栏（自动分类）占 5 份宽度，右栏（指定类目）占 7 份。
    两者视觉层级对等，都有明确的标题和功能说明。
    """

    def __init__(self, categories: list, parent=None) -> None:
        super().__init__(parent)
        self._categories = categories
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # ===== 左栏：自动分类 =====
        left_wrap = QFrame()
        left_wrap.setObjectName("DropColumn")
        left_layout = QVBoxLayout(left_wrap)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)

        left_title = QLabel("①  自动分类")
        left_title.setObjectName("DropColumnTitle")
        left_hint = QLabel("拖到这里，由程序智能判断类目")
        left_hint.setObjectName("DropColumnHint")
        left_layout.addWidget(left_title)
        left_layout.addWidget(left_hint)

        # 复用 DropZone，但让它撑满左栏
        self.drop_zone = DropZone()
        self.drop_zone.setMinimumHeight(120)
        left_layout.addWidget(self.drop_zone, stretch=1)

        layout.addWidget(left_wrap, stretch=5)

        # ===== 右栏：指定类目 =====
        right_wrap = QFrame()
        right_wrap.setObjectName("DropColumn")
        right_layout = QVBoxLayout(right_wrap)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(4)

        right_title = QLabel("②  指定类目（拖到对应卡片 = 强制归类）")
        right_title.setObjectName("DropColumnTitle")
        right_hint = QLabel("跳过自动分类，直接归到你选的类目")
        right_hint.setObjectName("DropColumnHint")
        right_layout.addWidget(right_title)
        right_layout.addWidget(right_hint)

        # 类目卡片栏（复用 CategoryDropBar）
        self.category_bar = CategoryDropBar(self._categories)
        right_layout.addWidget(self.category_bar)
        right_layout.addStretch()

        layout.addWidget(right_wrap, stretch=7)

    def update_categories(self, categories: list) -> None:
        """类目配置变更后刷新右侧卡片。"""
        self._categories = categories
        self.category_bar.update_categories(categories)
