"""archiver.py 测试：PDF 归档功能。"""

from __future__ import annotations

from pathlib import Path

from src.core.archiver import archive_invoices, _safe_dir_name
from src.core.categories import CategoryDef
from src.core.types import Invoice


def _make_pdf(tmp_path: Path, name: str) -> Path:
    """造一个最小的假 PDF 文件（只测试复制逻辑，不需要真实 PDF）。"""
    p = tmp_path / name
    p.write_bytes(b"%PDF-1.4 fake pdf content")
    return p


def test_safe_dir_name():
    """类目名含特殊字符时转成安全目录名。"""
    assert _safe_dir_name("差旅") == "差旅"
    assert _safe_dir_name("a/b:c*d") == "a_b_c_d"
    assert _safe_dir_name("") == "未分类"
    assert _safe_dir_name("   ") == "未分类"


def test_basic_archive(tmp_path: Path):
    """按类目归档，生成子目录 + 清单 CSV。"""
    pdf1 = _make_pdf(tmp_path, "hotel.pdf")
    pdf2 = _make_pdf(tmp_path, "reagent.pdf")
    out = tmp_path / "archive"
    invoices = [
        Invoice(file_path=str(pdf1), file_name="hotel.pdf", amount=500.0, category="差旅"),
        Invoice(file_path=str(pdf2), file_name="reagent.pdf", amount=200.0, category="材料"),
    ]
    cats = [CategoryDef(name="差旅", priority=1), CategoryDef(name="材料", priority=2)]
    result = archive_invoices(invoices, out, cats)

    assert (result / "差旅" / "hotel.pdf").exists()
    assert (result / "材料" / "reagent.pdf").exists()
    assert (result / "归档清单.csv").exists()


def test_no_category_goes_to_uncategorized(tmp_path: Path):
    """无类目/解析失败的发票归到「未分类」。"""
    pdf = _make_pdf(tmp_path, "bad.pdf")
    out = tmp_path / "archive"
    invoices = [
        Invoice(file_path=str(pdf), file_name="bad.pdf", amount=None, category=None, error="失败"),
    ]
    cats = [CategoryDef(name="差旅", priority=1)]
    result = archive_invoices(invoices, out, cats)
    assert (result / "未分类" / "bad.pdf").exists()


def test_missing_file_skipped(tmp_path: Path):
    """源文件不存在的发票跳过，不报错。"""
    out = tmp_path / "archive"
    invoices = [
        Invoice(file_path="nonexistent.pdf", file_name="ghost.pdf", amount=100.0, category="差旅"),
    ]
    cats = [CategoryDef(name="差旅", priority=1)]
    result = archive_invoices(invoices, out, cats)
    # 归档目录存在但差旅子目录可能不存在（没有成功复制的文件）
    assert result.exists()


def test_manifest_csv_content(tmp_path: Path):
    """归档清单 CSV 包含发票明细。"""
    import csv

    pdf = _make_pdf(tmp_path, "inv.pdf")
    out = tmp_path / "archive"
    invoices = [
        Invoice(
            file_path=str(pdf), file_name="inv.pdf", amount=888.88,
            category="差旅", invoice_no="12345678901234567890",
            seller_name="某酒店", issue_date="2026-08-11",
        ),
    ]
    cats = [CategoryDef(name="差旅", priority=1)]
    result = archive_invoices(invoices, out, cats)

    manifest = result / "归档清单.csv"
    with open(manifest, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert len(rows) == 1
    assert rows[0]["文件名"] == "inv.pdf"
    assert rows[0]["类目"] == "差旅"
    assert float(rows[0]["金额"]) == 888.88


def test_duplicate_filename_resolved(tmp_path: Path):
    """同名文件归档到同一目录时自动加序号。"""
    pdf1 = _make_pdf(tmp_path, "dup.pdf")
    # 复制一份到另一个位置（同文件名）
    pdf2 = tmp_path / "sub" / "dup.pdf"
    pdf2.parent.mkdir()
    pdf2.write_bytes(b"%PDF-1.4 another")
    out = tmp_path / "archive"
    invoices = [
        Invoice(file_path=str(pdf1), file_name="dup.pdf", amount=100.0, category="差旅"),
        Invoice(file_path=str(pdf2), file_name="dup.pdf", amount=200.0, category="差旅"),
    ]
    cats = [CategoryDef(name="差旅", priority=1)]
    result = archive_invoices(invoices, out, cats)
    # 应该有 dup.pdf 和 dup_1.pdf
    assert (result / "差旅" / "dup.pdf").exists()
    assert (result / "差旅" / "dup_1.pdf").exists()
