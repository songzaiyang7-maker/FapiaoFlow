# tests/fixtures

这里用于存放**脱敏的样例发票 PDF**，供集成测试使用。

## ⚠️ 重要：不要提交真实发票

真实发票包含敏感信息（发票号、销售方、购买方纳税人识别号等）。
**绝对不要**把你自己的真实发票 PDF 放到这里并提交到 git。

如果要贡献测试样例：

1. 用 reportlab 合成假发票（参考 `tests/test_integration.py` 的 `_make_pdf_bytes`）
2. 或对真实发票做脱敏处理（涂掉发票号、纳税人识别号、个人姓名）

## 当前状态

本目录目前为空。集成测试（`test_integration.py`）使用 reportlab 实时合成 PDF，不依赖外部文件。
