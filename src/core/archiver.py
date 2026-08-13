"""PDF 归档：把发票按类目复制到子文件夹，方便线下贴票。

输出目录结构：
    归档_20260811_153000/
    ├── 差旅/
    │   ├── 高铁票_杭州到上海.pdf
    │   └── 酒店住宿.pdf
    ├── 材料/
    │   └── 实验试剂.pdf
    ├── 市内交通/
    │   └── 滴滴打车.pdf
    ├── 未分类/              # 解析失败或无类目的发票
    │   └── 非发票文档.pdf
    └── 归档清单.csv          # 所有发票的明细汇总

只复制不移动——原始 PDF 文件保持不动，安全。
"""

from __future__ import annotations

import csv
import datetime
import logging
import shutil
from pathlib import Path

from src.core.categories import CategoryDef
from src.core.types import Invoice

logger = logging.getLogger(__name__)


def _safe_dir_name(name: str) -> str:
    """把类目名转成安全的文件夹名（去掉 Windows 禁用字符）。"""
    if not name:
        return "未分类"
    # Windows 禁用字符：\ / : * ? " < > |
    for ch in '\\/:*?"<>|':
        name = name.replace(ch, "_")
    return name.strip() or "未分类"


def archive_invoices(
    invoices: list[Invoice],
    output_dir: str | Path | None,
    categories: list[CategoryDef],
) -> Path:
    """把发票按类目复制到子文件夹。返回归档根目录。

    output_dir 为 None 时在当前目录下生成 归档_YYYYMMDD_HHMMSS/。
    """
    if output_dir is None:
        now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path.cwd() / f"归档_{now}"
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)

    valid_cat_names = {c.name for c in categories}
    archived = 0
    skipped_missing = 0
    skipped_no_category = 0
    manifest_rows: list[dict] = []

    for inv in invoices:
        src = Path(inv.file_path)
        if not src.exists():
            skipped_missing += 1
            logger.warning(f"归档跳过（文件不存在）: {inv.file_path}")
            continue

        # 决定子目录名
        if inv.category and inv.category in valid_cat_names:
            subdir = _safe_dir_name(inv.category)
        elif inv.category:
            # 类目不在当前配置里（被删了），仍按原类目名归档
            subdir = _safe_dir_name(inv.category)
        else:
            subdir = "未分类"
            skipped_no_category += 1

        dest_dir = root / subdir
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / inv.file_name

        # 同名文件冲突：追加序号
        if dest.exists():
            stem, suffix = dest.stem, dest.suffix
            i = 1
            while dest.exists():
                dest = dest_dir / f"{stem}_{i}{suffix}"
                i += 1

        try:
            shutil.copy2(src, dest)
            archived += 1
        except OSError as e:
            logger.warning(f"复制失败 {inv.file_path}: {e}")
            skipped_missing += 1
            continue

        manifest_rows.append({
            "文件名": inv.file_name,
            "类目": inv.category or "未分类",
            "金额": inv.amount if inv.amount is not None else "",
            "发票号": inv.invoice_no or "",
            "销售方": inv.seller_name or "",
            "日期": inv.issue_date or "",
            "状态": "❌ " + inv.error if inv.error else (
                "✋ 手动" if inv.user_overridden else (
                    "⚠ 待复核" if inv.confidence < 0.7 else "✓ 已分类"
                )
            ),
        })

    # 写归档清单 CSV
    manifest_path = root / "归档清单.csv"
    if manifest_rows:
        with open(manifest_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=manifest_rows[0].keys())
            writer.writeheader()
            writer.writerows(manifest_rows)

    logger.info(
        f"归档完成: {archived} 张成功, {skipped_missing} 张跳过(文件缺失), "
        f"{skipped_no_category} 张未分类 → {root}"
    )
    return root
