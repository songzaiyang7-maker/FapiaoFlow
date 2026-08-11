"""应用配色与样式表。"""

from __future__ import annotations

APP_STYLE = """
* {
    font-family: "Microsoft YaHei UI", "PingFang SC", "Segoe UI", sans-serif;
    font-size: 13px;
    color: #2c2c2c;
}

QMainWindow, QWidget {
    background-color: #fafafa;
}

/* 左侧 Session 面板 */
QFrame#SessionPanel {
    background-color: white;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
}

QLabel#PanelTitle {
    font-size: 15px;
    font-weight: 600;
    color: #2c2c2c;
    padding: 4px;
}

QListWidget#SessionList {
    background-color: transparent;
    outline: none;
}

QListWidget#SessionList::item {
    padding: 10px 8px;
    border-radius: 6px;
    margin: 2px 0;
    color: #444;
}

QListWidget#SessionList::item:selected {
    background-color: #e3eeff;
    color: #1a3a8a;
    border-left: 3px solid #4a6fff;
}

QListWidget#SessionList::item:hover {
    background-color: #f0f4ff;
}

QPushButton#PrimaryButton {
    background-color: #4a6fff;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 12px;
    font-weight: 500;
}

QPushButton#PrimaryButton:hover {
    background-color: #3a5fff;
}

/* 拖拽区容器：左右两栏 */
QFrame#DropColumn {
    background-color: transparent;
    border: none;
}

QLabel#DropColumnTitle {
    font-size: 14px;
    font-weight: 600;
    color: #2c2c2c;
    padding: 2px 0;
}

QLabel#DropColumnHint {
    font-size: 11px;
    color: #888;
    padding-bottom: 4px;
}

/* 自动分类拖拽区 */
QFrame#DropZone {
    background-color: #f0f4ff;
    border: 2px dashed #6c8cff;
    border-radius: 12px;
}

QFrame#DropZone:hover {
    background-color: #e6ecff;
    border-color: #4a6fff;
}

QLabel#DropZoneHint {
    font-size: 16px;
    color: #4a6fff;
    font-weight: 600;
}

QLabel#DropZoneSub {
    font-size: 11px;
    color: #888;
}

/* 通用按钮 */
QPushButton {
    background-color: #4a6fff;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 7px 14px;
}

QPushButton:hover {
    background-color: #3a5fff;
}

QPushButton:pressed {
    background-color: #2a4fff;
}

QPushButton#SecondaryButton {
    background-color: #e6e6e6;
    color: #333;
}

QPushButton#SecondaryButton:hover {
    background-color: #d6d6d6;
}

/* 表格 */
QTableView {
    background-color: white;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    gridline-color: #f0f0f0;
    selection-background-color: #d6e4ff;
    selection-color: #2c2c2c;
}

QHeaderView::section {
    background-color: #f5f5f5;
    padding: 8px;
    border: none;
    border-right: 1px solid #e0e0e0;
    border-bottom: 1px solid #e0e0e0;
    font-weight: 500;
}

/* 汇总栏 */
QFrame#SummaryBar {
    background-color: #fff8e1;
    border: 1px solid #ffe082;
    border-radius: 8px;
}

QLabel#SummaryLabel {
    font-size: 14px;
    font-weight: 500;
    padding: 4px 8px;
    color: #5d4037;
}

QLabel#TotalLabel {
    font-size: 16px;
    font-weight: 600;
    color: #c62828;
    padding: 4px 12px;
}

/* 状态栏 */
QStatusBar {
    background-color: transparent;
    color: #666;
}
"""

