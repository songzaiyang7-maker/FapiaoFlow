"""主窗口：三栏布局。

左侧：SessionPanel（日期导航）
中间：DropZone（自动分类） + CategoryDropBar（拖到具体类目） + 表格 + 汇总栏
右侧/底部：操作按钮（导出、清空）+ 菜单栏（设置 → 类目管理）

类目配置可由用户自定义（categories.json），主窗口在类目变更后刷新所有依赖组件。
"""

from __future__ import annotations

import datetime

from PyQt6.QtCore import Qt, QThreadPool
from PyQt6.QtGui import QAction, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStatusBar,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from src.core.archiver import archive_invoices
from src.core.categories import CategoryDef, CategoryStore
from src.core.exporter import export_to_excel
from src.core.pipeline import reset_classifier
from src.core.storage import SessionStore
from src.core.totals import compute_totals
from src.core.types import Invoice
from src.gui.category_dialog import CategoryManagerDialog
from src.gui.delegates import CategoryDelegate
from src.gui.drop_area import DropArea
from src.gui.session_panel import SessionPanel
from src.gui.styles import APP_STYLE
from src.gui.table_model import InvoiceTableModel
from src.gui.workers import ParseTask


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("发票分拣助手 · FapiaoFlow")
        self.resize(1280, 760)
        self.setStyleSheet(APP_STYLE)

        self.category_store = CategoryStore()
        self._categories: list[CategoryDef] = self.category_store.list()
        self.store = SessionStore()
        self.thread_pool = QThreadPool(self)
        self.thread_pool.setMaxThreadCount(4)

        # 并发任务计数（修原 CRITICAL #1）：
        # _active_tasks 是单调递增的总数，_done 是已完成数。
        # 不再用 task 携带的 total——多批次拖入时计数不会混乱。
        self._active_tasks = 0
        self._done_tasks = 0

        self._current_session_id: str | None = None
        # 编辑类目时挂起 session_panel 刷新（修原 #11）
        self._suspending_session_refresh = False

        self._build_ui()
        self._build_menu()
        self._connect_signals()
        self._load_initial_session()

    # ---------- UI 构建 ----------
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        # 左侧 Session 栏
        self.session_panel = SessionPanel()
        root.addWidget(self.session_panel)

        # 右侧主区
        main = QVBoxLayout()
        main.setSpacing(10)

        # 顶部：拖拽区（左右两栏：自动分类 + 指定类目）
        self.drop_area = DropArea(self._categories)
        main.addWidget(self.drop_area)

        # 操作按钮栏
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.clear_btn = QPushButton("清空当前记录")
        self.clear_btn.setObjectName("SecondaryButton")
        self.export_btn = QPushButton("导出 Excel")
        self.archive_btn = QPushButton("📁 归档 PDF")
        self.archive_btn.setObjectName("SecondaryButton")
        btn_row.addWidget(self.clear_btn)
        btn_row.addWidget(self.archive_btn)
        btn_row.addWidget(self.export_btn)
        main.addLayout(btn_row)

        # 表格
        self.table = QTableView()
        self.model = InvoiceTableModel()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(
            0, self.table.horizontalHeader().ResizeMode.Stretch
        )
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(2, 110)
        self.table.setColumnWidth(3, 180)
        self.table.setColumnWidth(4, 220)
        self.table.setColumnWidth(5, 100)
        self.table.setColumnWidth(6, 220)
        self.category_delegate = CategoryDelegate(self._category_names(), self.table)
        self.table.setItemDelegateForColumn(1, self.category_delegate)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_table_context_menu)
        self.delete_sc = QShortcut(QKeySequence(Qt.Key.Key_Delete), self.table)
        self.delete_sc.activated.connect(self._delete_selected_rows)
        self.table.doubleClicked.connect(self._on_open_pdf)
        main.addWidget(self.table, stretch=1)

        # 汇总栏（类目从配置动态生成）
        self.summary_bar = QWidget()
        self.summary_bar.setObjectName("SummaryBar")
        self.summary_bar.setFixedHeight(60)
        self._summary_layout = QHBoxLayout(self.summary_bar)
        self._summary_layout.setContentsMargins(12, 8, 12, 8)
        self.summary_labels: dict[str, QLabel] = {}
        self._rebuild_summary_labels()
        self.total_label = QLabel("总计: ¥0.00")
        self.total_label.setObjectName("TotalLabel")
        self._summary_layout.addWidget(self.total_label)
        main.addWidget(self.summary_bar)

        # 状态栏 + 进度条
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("就绪")
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setFixedWidth(200)
        self.status.addPermanentWidget(self.progress)

        root.addLayout(main, stretch=1)

    def _rebuild_summary_labels(self) -> None:
        """根据当前类目重建汇总栏的 label。"""
        # 清除旧 label
        for lbl in self.summary_labels.values():
            self._summary_layout.removeWidget(lbl)
            lbl.deleteLater()
        self.summary_labels.clear()
        # 按类目顺序新建
        for cat in self._categories:
            lbl = QLabel(f"{cat.name}: ¥0.00")
            lbl.setObjectName("SummaryLabel")
            self.summary_labels[cat.name] = lbl
            self._summary_layout.addWidget(lbl)
        self._summary_layout.addStretch()

    def _category_names(self) -> list[str]:
        return [c.name for c in self._categories]

    def _build_menu(self) -> None:
        menubar = self.menuBar()
        menu_settings = menubar.addMenu("设置")
        self.action_manage_categories = QAction("类目管理…", self)
        self.action_manage_categories.triggered.connect(self._on_manage_categories)
        menu_settings.addAction(self.action_manage_categories)
        menu_settings.addSeparator()
        # OCR 开关（可勾选）
        from src.core.config import load_ocr_enabled
        self.action_toggle_ocr = QAction("OCR 识别扫描件", self, checkable=True)
        self.action_toggle_ocr.setChecked(load_ocr_enabled())
        self.action_toggle_ocr.toggled.connect(self._on_toggle_ocr)
        menu_settings.addAction(self.action_toggle_ocr)

    def _on_toggle_ocr(self, enabled: bool) -> None:
        """切换 OCR 开关。"""
        import os
        os.environ["OCR_ENABLED"] = "true" if enabled else "false"
        label = "开启" if enabled else "关闭"
        self.status.showMessage(f"OCR 已{label}（下次处理扫描件时生效）", 5000)

    def _connect_signals(self) -> None:
        self.drop_area.drop_zone.paths_selected.connect(self._on_paths_auto)
        self.drop_area.category_bar.paths_dropped.connect(self._on_paths_to_category)
        self.export_btn.clicked.connect(self._on_export)
        self.archive_btn.clicked.connect(self._on_archive)
        self.clear_btn.clicked.connect(self._on_clear)
        self.session_panel.session_selected.connect(self._on_session_selected)
        self.session_panel.new_session_requested.connect(self._on_new_session)
        self.session_panel.delete_session_requested.connect(self._on_delete_session)
        self.session_panel.rename_requested.connect(self._on_rename_session)
        self.model.dataChanged.connect(lambda *_: self._on_invoices_changed())
        self.model.rowsInserted.connect(lambda *_: self._on_invoices_changed())
        self.model.rowsRemoved.connect(lambda *_: self._on_invoices_changed())
        self.model.modelReset.connect(lambda: self._on_invoices_changed())

    def _load_initial_session(self) -> None:
        """启动时加载最近的 session，无则自动新建一个。"""
        sessions = self.store.list_sessions()
        if not sessions:
            s = SessionStore.new_session()
            self.store.save_session(s)
            sessions = [s]
        self.session_panel.refresh(sessions, current_id=sessions[0].id)
        self._switch_to_session(sessions[0].id)

    # ---------- 类目管理 ----------
    def _on_manage_categories(self) -> None:
        """打开类目管理对话框。"""
        # 统计当前 session 各类目发票数
        invoices = self.model.all_invoices()
        counts: dict[str, int] = {}
        for inv in invoices:
            if inv.category:
                counts[inv.category] = counts.get(inv.category, 0) + 1

        dlg = CategoryManagerDialog(self._categories, counts, self)
        if dlg.exec() != dlg.DialogCode.Accepted:
            return

        new_cats = dlg.result_categories()
        migration = dlg.migration  # (被删类目, 迁移目标) 或 None

        # 处理迁移：把当前 session 里属于被删类目的发票改到目标类目
        if migration:
            old_name, new_name = migration
            self.model.reassign_category(old_name, new_name)
            # 同时迁移所有 session 的历史数据
            self._migrate_all_sessions(old_name, new_name)

        # 同步重命名（类目改名时，旧发票的 category 字符串要跟着改）
        # 通过 priority 配对——编辑面板改 name 不改 priority
        self._sync_renames(self._categories, new_cats)

        # 保存到 categories.json
        self.category_store.replace_all(new_cats)
        self.category_store.save()
        self._categories = self.category_store.list()

        # 刷新所有依赖组件
        self._refresh_after_category_change()
        # 重置分类器单例（让后续解析用新类目）
        reset_classifier()
        self.status.showMessage(f"类目已更新（共 {len(self._categories)} 类）", 5000)

    def _migrate_all_sessions(self, old_name: str, new_name: str) -> None:
        """把所有 session 里属于 old_name 的发票改到 new_name。"""
        for s in self.store.list_sessions():
            changed = False
            for inv in s.invoices:
                if inv.category == old_name:
                    inv.category = new_name
                    changed = True
            if changed:
                self.store.save_session(s)

    def _sync_renames(self, old_cats: list[CategoryDef], new_cats: list[CategoryDef]) -> None:
        """检测类目改名，把所有 session 里旧名发票改成新名。

        通过 priority 配对（编辑面板改名不改 priority）。
        """
        old_by_priority = {c.priority: c.name for c in old_cats}
        new_by_priority = {c.priority: c.name for c in new_cats}
        renames: list[tuple[str, str]] = []
        for priority, old_name in old_by_priority.items():
            new_name = new_by_priority.get(priority)
            if new_name and new_name != old_name:
                renames.append((old_name, new_name))
        for old_name, new_name in renames:
            self._migrate_all_sessions(old_name, new_name)

    def _refresh_after_category_change(self) -> None:
        """类目变更后刷新所有依赖组件。"""
        # 拖拽区（左右两栏：自动分类区不受影响，只刷新右侧类目卡片）
        self.drop_area.update_categories(self._categories)
        # 表格 delegate
        self.category_delegate.set_categories(self._category_names())
        # 汇总栏
        self._rebuild_summary_labels()
        self._refresh_summary()
        # 刷新表格显示（类目改名后行内容变了）
        if self.model.all_invoices():
            self.model.begin_batch()
            self.model.end_batch()
        # 刷新左侧 session 列表（金额/张数可能变）
        sessions = self.store.list_sessions()
        self.session_panel.refresh(sessions, current_id=self._current_session_id)

    # ---------- Session 操作 ----------
    def _on_session_selected(self, sid: str) -> None:
        self._switch_to_session(sid)

    def _on_new_session(self) -> None:
        from PyQt6.QtWidgets import QInputDialog

        label, ok = QInputDialog.getText(self, "新建记录", "备注（可留空，如：出差北京）：")
        if not ok:
            return
        s = SessionStore.new_session(label=label.strip())
        self.store.save_session(s)
        sessions = self.store.list_sessions()
        self.session_panel.refresh(sessions, current_id=s.id)
        self._switch_to_session(s.id)

    def _on_delete_session(self, sid: str) -> None:
        ret = QMessageBox.question(
            self,
            "删除记录",
            "确定删除这条记录吗？（仅删除工具内记录，不影响原始 PDF 文件）",
        )
        if ret != QMessageBox.StandardButton.Yes:
            return
        self.store.remove_session(sid)
        sessions = self.store.list_sessions()
        if not sessions:
            s = SessionStore.new_session()
            self.store.save_session(s)
            sessions = [s]
        self.session_panel.refresh(sessions, current_id=sessions[0].id)
        self._switch_to_session(sessions[0].id)

    def _on_rename_session(self, sid: str) -> None:
        from PyQt6.QtWidgets import QInputDialog

        s = self.store.get_session(sid)
        if s is None:
            return
        label, ok = QInputDialog.getText(
            self, "编辑备注", "备注（可留空，如：出差北京）：", text=s.label
        )
        if not ok:
            return
        s.label = label.strip()
        self.store.save_session(s)
        sessions = self.store.list_sessions()
        self.session_panel.refresh(sessions, current_id=sid)

    def _switch_to_session(self, sid: str) -> None:
        s = self.store.get_session(sid)
        if s is None:
            return
        self._current_session_id = sid
        self.model.set_invoices(s.invoices)
        self._refresh_summary()

    def _on_invoices_changed(self) -> None:
        """表格数据变化时同步到当前 session 并持久化。"""
        if self._current_session_id is None:
            return
        s = self.store.get_session(self._current_session_id)
        if s is None:
            return
        s.invoices = self.model.all_invoices()
        self.store.save_session(s)
        self._refresh_summary()
        # 编辑类目时挂起左侧列表刷新（修原 #11），避免 delegate 编辑被打断
        if self._suspending_session_refresh:
            return
        # 否则原地更新左侧当前项的显示文本（不 clear+rebuild，避免扰动）
        self._update_current_session_list_item()

    def _update_current_session_list_item(self) -> None:
        """只更新左侧列表中当前 session 那一项的文本，不重建整个列表。"""
        if self._current_session_id is None:
            return
        list_widget = self.session_panel.list_widget
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == self._current_session_id:
                s = self.store.get_session(self._current_session_id)
                if s:
                    item.setText(self.session_panel._format_label(s))
                break

    # ---------- PDF 拖入处理 ----------
    def _on_paths_auto(self, paths: list[str]) -> None:
        """拖到主区：自动分类。"""
        self._start_processing(paths, force_category=None)

    def _on_paths_to_category(self, paths: list[str], category_name: str) -> None:
        """拖到具体类目按钮：强制归该类。"""
        if category_name not in self._category_names():
            QMessageBox.warning(self, "类目无效", f"类目「{category_name}」不存在。")
            return
        self._start_processing(paths, force_category=category_name)

    def _start_processing(self, paths: list[str], force_category: str | None) -> None:
        """启动 PDF 处理任务。

        并发计数模型（修原 CRITICAL #1）：
        - _active_tasks：累计本次会话提交的总任务数（不减）
        - _done_tasks：累计已完成数
        - 进度条 range = (0, _active_tasks)，value = _done_tasks
        - 多批次拖入时 _active_tasks 继续累加，计数单调，不会因旧批次的 total 回调错乱
        """
        if not paths:
            return
        self._active_tasks += len(paths)
        self.progress.setRange(0, max(self._active_tasks, 1))
        self.progress.setValue(self._done_tasks)
        self.progress.setVisible(True)
        mode_label = "人工归类" if force_category else "自动分类"
        pending = self._active_tasks - self._done_tasks
        self.status.showMessage(
            f"正在处理 {len(paths)} 张发票（{mode_label}）· 共 {pending} 张待处理..."
        )

        for path in paths:
            task = ParseTask(path)
            task.signals.parsed.connect(
                lambda inv, fc=force_category: self._on_parsed(inv, fc)
            )
            task.signals.finished_one.connect(self._on_task_finished)
            self.thread_pool.start(task)

    def _on_parsed(self, inv: Invoice, force_category: str | None) -> None:
        if force_category is not None:
            # 强制归类：覆盖自动结果
            inv.category = force_category
            inv.confidence = 1.0
            inv.note = f"人工归类：{force_category}"
            inv.user_overridden = True
        self.model.add_invoice(inv)

    def _on_task_finished(self) -> None:
        """单个任务完成（不管成功失败）。"""
        self._done_tasks += 1
        self.progress.setValue(self._done_tasks)
        if self._done_tasks >= self._active_tasks:
            # 全部完成
            self.progress.setVisible(False)
            summary = self._summarize_batch()
            self.status.showMessage(f"完成 {self._active_tasks} 张 · 当前记录：{summary}")
            self._active_tasks = 0
            self._done_tasks = 0

    def _summarize_batch(self) -> str:
        """汇总当前 session 的发票分布，供处理后状态栏显示。"""
        from collections import Counter

        invoices = self.model.all_invoices()
        cats: Counter = Counter()
        failed = 0
        for inv in invoices:
            if inv.error:
                failed += 1
            elif inv.category:
                cats[inv.category] += 1
        # 按当前类目顺序输出
        parts = [f"{cat.name} {cats.get(cat.name, 0)}" for cat in self._categories if cats.get(cat.name, 0) > 0]
        summary = " / ".join(parts) if parts else "无有效分类"
        if failed > 0:
            summary += f"，失败 {failed} 张"
        return summary

    def _on_open_pdf(self, index) -> None:
        """双击表格行用系统默认程序打开 PDF。"""
        import os
        import sys

        inv = self.model.get_invoice(index.row())
        if inv is None:
            return
        path = inv.file_path
        if not path or not os.path.exists(path):
            QMessageBox.warning(self, "无法打开", f"文件不存在：\n{path}")
            return
        try:
            if sys.platform == "win32":
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["open", path])
            else:
                import subprocess
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            QMessageBox.warning(self, "打开失败", str(e))

    # ---------- 汇总 ----------
    def _refresh_summary(self) -> None:
        invoices = self.model.all_invoices()
        totals = compute_totals(invoices, self._categories)
        for cat in self._categories:
            if cat.name in self.summary_labels:
                self.summary_labels[cat.name].setText(f"{cat.name}: ¥{totals[cat.name]:,.2f}")
        self.total_label.setText(f"总计: ¥{totals['总计']:,.2f}")

    # ---------- 导出 / 清空 ----------
    def _on_export(self) -> None:
        invoices = self.model.all_invoices()
        if not invoices:
            QMessageBox.information(self, "无数据", "当前记录没有发票可导出。")
            return
        now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"fapiao_summary_{now}.xlsx"
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self, "导出 Excel", default_name, "Excel 文件 (*.xlsx)"
        )
        if not path:
            return
        try:
            output = export_to_excel(invoices, self._categories, output_path=path)
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))
            return
        ret = QMessageBox.question(
            self,
            "导出成功",
            f"已导出到：\n{output}\n\n是否打开所在文件夹？",
        )
        if ret == QMessageBox.StandardButton.Yes:
            import os
            import subprocess
            import sys

            folder = os.path.dirname(os.path.abspath(output))
            try:
                if sys.platform == "win32":
                    subprocess.run(["explorer", f"/select,{output}"], check=False)
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", folder])
                else:
                    subprocess.Popen(["xdg-open", folder])
            except Exception as e:
                self.status.showMessage(f"打开文件夹失败：{e}")
        else:
            self.status.showMessage(f"已导出: {output}")

    def _on_archive(self) -> None:
        """归档 PDF：按类目复制到子文件夹。"""
        invoices = self.model.all_invoices()
        if not invoices:
            QMessageBox.information(self, "无数据", "当前记录没有发票可归档。")
            return
        from PyQt6.QtWidgets import QFileDialog
        now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        default_dir = f"归档_{now}"
        path = QFileDialog.getExistingDirectory(
            self, "选择归档输出文件夹", default_dir
        )
        if not path:
            return
        try:
            output = archive_invoices(invoices, path, self._categories)
        except Exception as e:
            QMessageBox.critical(self, "归档失败", str(e))
            return
        # 统计各类目归档数
        from collections import Counter
        cat_counts: Counter = Counter()
        for inv in invoices:
            if inv.category:
                cat_counts[inv.category] += 1
        summary = " / ".join(
            f"{cat.name} {cat_counts.get(cat.name, 0)}" for cat in self._categories
            if cat_counts.get(cat.name, 0) > 0
        )
        ret = QMessageBox.question(
            self,
            "归档成功",
            f"已归档到：\n{output}\n\n{summary}\n\n是否打开归档文件夹？",
        )
        if ret == QMessageBox.StandardButton.Yes:
            import subprocess
            import sys
            try:
                if sys.platform == "win32":
                    subprocess.run(["explorer", str(output)], check=False)
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", str(output)])
                else:
                    subprocess.Popen(["xdg-open", str(output)])
            except Exception as e:
                self.status.showMessage(f"打开文件夹失败：{e}")
        else:
            self.status.showMessage(f"已归档到: {output}")

    def _on_clear(self) -> None:
        if not self.model.all_invoices():
            return
        ret = QMessageBox.question(
            self,
            "清空当前记录",
            "确定清空当前记录下所有发票吗？（不会删除原始 PDF；如想删除整条记录请在左侧右键）",
        )
        if ret == QMessageBox.StandardButton.Yes:
            self.model.clear()

    # ---------- 表格右键菜单 / 删除 ----------
    def _on_table_context_menu(self, pos) -> None:
        index = self.table.indexAt(pos)
        if not index.isValid():
            return
        selected_rows = sorted({i.row() for i in self.table.selectionModel().selectedRows()})
        if not selected_rows:
            selected_rows = [index.row()]

        menu = QMenu(self.table)
        n = len(selected_rows)
        act_delete = menu.addAction(f"删除选中行（{n} 张）" if n > 1 else "删除此行")
        menu.addSeparator()
        submenu = menu.addMenu("改类目为…")
        for cat in self._categories:
            submenu.addAction(
                cat.name,
                lambda checked=False, c=cat.name: self._set_rows_category(selected_rows, c),
            )
        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        if action is act_delete:
            self._delete_rows(selected_rows)

    def _delete_selected_rows(self) -> None:
        selected = sorted({i.row() for i in self.table.selectionModel().selectedRows()})
        if selected:
            self._delete_rows(selected)

    def _delete_rows(self, rows: list[int]) -> None:
        n = len(rows)
        if n == 0:
            return
        names = []
        for r in rows:
            inv = self.model.get_invoice(r)
            if inv:
                names.append(inv.file_name)
        detail = "、".join(names[:3])
        if len(names) > 3:
            detail += f" 等 {len(names)} 个"
        ret = QMessageBox.question(
            self, "删除确认", f"确定删除 {detail} 吗？（不会动原始 PDF）"
        )
        if ret == QMessageBox.StandardButton.Yes:
            removed = self.model.remove_rows(rows)
            self.status.showMessage(f"已删除 {removed} 行")

    def _set_rows_category(self, rows: list[int], category_name: str) -> None:
        """批量改类目（用 begin_batch/end_batch 只触发一次持久化）。"""
        self.model.begin_batch()
        try:
            for r in rows:
                self.model.set_category_for_row(r, category_name)
        finally:
            self.model.end_batch()
        self.status.showMessage(f"已将 {len(rows)} 行改为 {category_name}")
