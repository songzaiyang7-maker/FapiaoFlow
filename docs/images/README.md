# 截图说明

README 引用的截图都放在这个目录（`docs/images/`）。

## 需要的截图

| 文件名 | 内容 | 用在哪 |
|--------|------|--------|
| `main-screenshot.png` | 主界面全貌（拖拽区 + 类目按钮 + 表格 + 汇总栏） | README 首屏 |
| `category-manager.png`（可选） | 类目管理对话框 | README 类目设计章节 |
| `excel-export.png`（可选） | 导出的 Excel 报销汇总表 | README 使用流程 |

## 怎么截图

1. **启动应用**：双击桌面 `FapiaoFlow.exe`，或 `python main.py`
2. **准备测试数据**：建议用合成 PDF（见 `tests/test_integration.py` 的 `_make_pdf_bytes`），
   或对真实发票**严格打码**：发票号、姓名、身份证号、纳税人识别号、购买方名称
3. **截图工具**：Windows 用 `Win + Shift + S`（截图工具）或 `Win + PrtScn`（全屏保存到 图片/屏幕截图）
4. **保存到**：`docs/images/main-screenshot.png` 等对应文件名

## ⚠️ 截图前必看

**不要在截图里暴露任何敏感信息**：

- ❌ 真实姓名（如发票上的"开票人""出行人"）
- ❌ 发票号码（20 位数字）
- ❌ 纳税人识别号 / 统一社会信用代码
- ❌ 身份证号（即使是脱敏的 `3301082005****021X` 也建议涂掉）
- ❌ 真实公司名（除非是公开的滴滴/京东这种大平台）
- ❌ 你的 API key（如果截图设置/配置相关）

最稳的做法：用几张**合成 PDF** 测试，截图里全是假数据。

## 没截图前 README 会怎样？

README 里引用了 `docs/images/main-screenshot.png`，如果该文件不存在，
GitHub 上会显示一个"图片加载失败"的占位符。截图后放进目录、提交推送即可正常显示，
不需要改 README。
