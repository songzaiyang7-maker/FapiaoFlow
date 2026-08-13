"""PDF 文本提取。

电子发票（文字可选 PDF）：用 pdfplumber 直接提取，快且准。
扫描件（图片型 PDF）：pdfplumber 提取为空时，回退到 OCR（RapidOCR）。

设计：
- 电子发票走 pdfplumber 快路径（不变）
- 文字为空 → 判定扫描件 → pypdfium2 渲染成图片 → RapidOCR 识别
- OCR 不可用（没装包/被禁用）→ 返回空字符串（现有契约不变）
- 解密 PDF 抛 ParseError
"""

from __future__ import annotations

import logging
from pathlib import Path

import pdfplumber
from pdfminer.pdfdocument import PDFPasswordIncorrect

PathLike = str | Path

logger = logging.getLogger(__name__)

# OCR 引擎懒加载（首次 OCR 时才 import + 初始化，避免启动变慢）
_ocr_engine = None
_ocr_checked = False


def _is_ocr_available() -> bool:
    """检查 OCR 依赖是否可用。"""
    global _ocr_checked
    if _ocr_checked:
        return _ocr_engine is not None
    _ocr_checked = True
    try:
        import pypdfium2  # noqa: F401
        from rapidocr_onnxruntime import RapidOCR  # noqa: F401
        return True
    except ImportError as e:
        logger.info(f"OCR 依赖不可用（扫描件将无法识别）: {e}")
        return False


def _get_ocr_engine():
    """懒加载获取 OCR 引擎实例。返回 None 表示不可用。"""
    global _ocr_engine
    if _ocr_engine is not None:
        return _ocr_engine
    if not _is_ocr_available():
        return None
    try:
        from rapidocr_onnxruntime import RapidOCR
        _ocr_engine = RapidOCR()
        logger.info("OCR 引擎初始化成功")
        return _ocr_engine
    except Exception as e:
        logger.warning(f"OCR 引擎初始化失败: {e}")
        return None


def _ocr_pdf(path: Path) -> str:
    """对扫描件 PDF 做 OCR，返回识别出的文本。

    用 pypdfium2 把每页渲染成 300dpi 图片，喂给 RapidOCR。
    若 OCR_ENABLED=false 或依赖不可用，返回空字符串。
    """
    # 检查 OCR 开关
    from src.core.config import load_ocr_enabled
    if not load_ocr_enabled():
        logger.info("OCR 已被禁用（OCR_ENABLED=false），跳过扫描件识别")
        return ""

    import pypdfium2 as pdfium

    engine = _get_ocr_engine()
    if engine is None:
        return ""

    try:
        pdf = pdfium.PdfDocument(str(path))
    except Exception as e:
        logger.warning(f"OCR 打开 PDF 失败 {path}: {e}")
        return ""

    chunks: list[str] = []
    try:
        for i in range(len(pdf)):
            try:
                page = pdf[i]
                # 渲染成 300dpi 图片（scale=2 约等于 144dpi，发票够清晰）
                bitmap = page.render(scale=2)
                pil_image = bitmap.to_pil()
                # RapidOCR 接受 PIL Image 或 ndarray
                result, _elapsed = engine(np_array_from_pil(pil_image))
                if result:
                    # result 是 [[bbox, text, score], ...]，只取 text
                    texts = [item[1] for item in result if item and len(item) > 1]
                    if texts:
                        chunks.append("\n".join(texts))
            except Exception as e:
                logger.warning(f"OCR 第 {i + 1} 页失败 {path}: {e}")
                continue
    finally:
        pdf.close()

    return "\n".join(chunks)


def np_array_from_pil(pil_image):
    """PIL Image → numpy ndarray（RapidOCR 需要 ndarray 输入）。"""
    import numpy as np
    return np.array(pil_image)


class ParseError(Exception):
    """PDF 解析失败。"""


def extract_text(path: PathLike) -> str:
    """从 PDF 提取纯文本。

    流程：
    1. pdfplumber 提取文字（电子发票快路径）
    2. 文字为空 → 判定扫描件 → OCR 回退
    3. OCR 也失败/不可用 → 返回空字符串

    失败情况：
    - 文件不存在 / 不是 PDF：抛 ParseError
    - PDF 加密：抛 ParseError
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
            text = "\n".join(chunks)
    except PDFPasswordIncorrect as e:
        raise ParseError(f"PDF 加密，需要密码: {p}") from e
    except Exception as e:
        raise ParseError(f"PDF 解析失败 {p}: {e}") from e

    # 电子发票：有文字直接返回
    if text.strip():
        return text

    # 扫描件：文字为空，尝试 OCR
    logger.info(f"PDF 未提取到文字，尝试 OCR: {p.name}")
    ocr_text = _ocr_pdf(p)
    if ocr_text.strip():
        logger.info(f"OCR 识别成功: {p.name}（{len(ocr_text)} 字符）")
        return ocr_text

    # OCR 也失败
    logger.warning(f"OCR 未能识别文字: {p.name}")
    return ""


def is_scanner_pdf(path: PathLike) -> bool:
    """快速判断 PDF 是否是扫描件（文字提取为空）。

    用于 UI 提示用户"这张是扫描件，需要 OCR"。
    不做 OCR，只检查 pdfplumber 能否提取到文字。
    """
    p = Path(path)
    if not p.exists():
        return False
    try:
        with pdfplumber.open(str(p)) as pdf:
            for page in pdf.pages:
                if (page.extract_text() or "").strip():
                    return False  # 有文字，不是扫描件
        return True  # 所有页都没文字
    except Exception:
        return False
