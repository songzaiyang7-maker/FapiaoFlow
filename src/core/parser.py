"""PDF 文本提取，基于 pdfplumber。

电子发票（如携程/京东/滴滴发送的 PDF）通常是文字可选的，
pdfplumber 直接 extract_text 即可。

设计：
- 单页/多页 PDF 都把文本拼成单个字符串返回
- 解析失败抛 ParseError，调用方捕获后写入 Invoice.error
- 不做 OCR —— 用户已确认本期只支持电子发票（文字可选）
"""

from __future__ import annotations

from pathlib import Path

import pdfplumber
from pdfminer.pdfdocument import PDFPasswordIncorrect

PathLike = str | Path


class ParseError(Exception):
    """PDF 解析失败。"""


def extract_text(path: PathLike) -> str:
    """从 PDF 提取纯文本。

    失败情况：
    - 文件不存在 / 不是 PDF：抛 ParseError
    - PDF 加密：抛 ParseError
    - 文字提取为空（可能是扫描件）：返回空字符串，调用方判断
    """
    p = Path(path)
    if not p.exists():
        raise ParseError(f"文件不存在: {p}")

    try:
        with pdfplumber.open(str(p)) as pdf:
            chunks: list[str] = []
            for page in pdf.pages:
                text = page.extract_text() or ""
                chunks.append(text)
            return "\n".join(chunks)
    except PDFPasswordIncorrect as e:
        raise ParseError(f"PDF 加密，需要密码: {p}") from e
    except Exception as e:
        raise ParseError(f"PDF 解析失败 {p}: {e}") from e
