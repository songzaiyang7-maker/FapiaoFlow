"""后台并发处理 PDF 的 worker。

每个 PDF 一个 ParseTask（QRunnable），丢进 QThreadPool 并发执行。
通过 Qt 信号把结果回主线程更新表格。

设计：task 只负责解析并发结果，不携带 index/total——进度计数由主窗口
统一维护（修原 CRITICAL：多批次拖入时 total 混乱）。

最大并发数 4（PDF 解析是 IO+CPU 混合，太高反而抢资源）。
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QObject, QRunnable, pyqtSignal

from src.core.pipeline import process_one_pdf
from src.core.types import Invoice


class _Signals(QObject):
    """QRunnable 不能多继承，所以信号放独立的 QObject。

    每个 task 一组信号实例。
    """

    parsed = pyqtSignal(object)    # Invoice
    finished_one = pyqtSignal()    # 无参：本 task 完成（不管成功失败）


class ParseTask(QRunnable):
    """单张 PDF 的解析任务。

    构造只接收 path；进度计数由主窗口在 finished_one 信号上统一累加。
    """

    def __init__(self, path: str) -> None:
        super().__init__()
        self.path = path
        self.signals = _Signals()
        self.setAutoDelete(True)

    def run(self) -> None:  # type: ignore[override]
        try:
            inv = process_one_pdf(self.path)
            self.signals.parsed.emit(inv)
        except Exception as e:
            # pipeline 内部应该 catch 所有错误，但兜底
            # 用 Path.name() 取文件名——Windows 反斜杠路径 split("/") 会失败
            inv = Invoice(
                file_path=self.path,
                file_name=Path(self.path).name,
                error=f"未捕获异常: {e}",
            )
            self.signals.parsed.emit(inv)
        finally:
            self.signals.finished_one.emit()
