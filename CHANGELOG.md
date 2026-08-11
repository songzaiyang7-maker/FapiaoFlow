# 更新日志

本项目遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### 计划中
- OCR 支持（扫描件）
- 按类目自动归档 PDF 到子文件夹
- 设置对话框：UI 上切换 backend 模式

## [0.2.0] - 2026-08-11

### 新增
- **自定义类目**：用户可在「设置 → 类目管理」中自由增删改类目（类目名、关键词、颜色、优先级）
- 类目配置持久化到 `data/categories.json`，支持直接编辑文件
- 新增 `src/core/categories.py`：`CategoryDef` + `CategoryStore`
- 新增 `src/gui/category_dialog.py`：类目管理对话框
- 支持红字发票（冲红/退款）负数金额提取
- 补充测试：新增 `test_storage.py` / `test_categories.py`，测试总数从 47 增至 75

### 修复
- **[critical] 修复多批次拖入 PDF 时进度条计数错乱**（原 `_pending_done_offset` 在 `__init__` 未初始化，旧批次回调的 total 会污染进度）
- **[critical] 修复类目改名后旧数据加载失败导致所有历史记录消失**（`Invoice.category` 从枚举改为字符串，不再做 `Category(...)` 转换）
- **[high] 修复 Windows 下兜底异常分支文件名显示为完整路径**（`split("/")` → `Path.name()`）
- **[high] 修复 LLM 分类器无超时导致卡死**（OpenAI client 加 `timeout=30.0`）
- **[high] 修复红字发票金额被错误取成正数或解析失败**（正则支持前导负号）
- **[high] 修复 8 位老式发票号被漏提取**（`\d{20}` → `\d{8,20}`）
- **[high] 修复销售方名称误匹配购买方**（真实打车发票"购 名称：A 销 名称：B"同行布局下，原正则会先撞到购买方名。改为带 `[销售]` 前缀的精确匹配 + `_is_likely_buyer` 启发式过滤）
- **[high] 修复发票号/开票日期跨行丢失**（真实酒店发票"发票号码：\\n...\\n制 26112..."这种字段值不在标签同行的布局，原正则匹配不到。改为跨行 `.*?(\d{18,20})` 匹配）
- **[high] 修复极端分散布局下销售方提取失败**（真实酒店发票"某大学 北京XX酒店公司"无标签同行，靠公司特征词如"有限公司/酒店/集团"兜底识别）
- **[high] 修复编辑类目时左侧列表重建可能干扰 delegate**（加 `_suspending_session_refresh` flag，原地更新单行）
- **[medium] 修复批量改类目时每行触发一次磁盘写**（新增 `begin_batch/end_batch`）
- **[medium] 修复 `compute_totals` 在类目被删后静默漏算金额**（归入"未分类"桶）
- **[medium] 修复 Session 列表同日期排序不稳定**（改 `(date, id)` 复合排序）
- **[medium] 修复损坏的 sessions.json 导致整个加载失败**（单条 session 解析失败跳过其余）
- **[low] 修复 exporter 列字母 `chr(64+i)` 超过 26 列出错**（改用 `get_column_letter`）
- **[low] 修复 parser 依赖 `pdfplumber.pdfminer` 实现细节**（改显式 import）
- **[low] 修复 config 多余的 `load_dotenv()` 兜底可能误读父目录 .env**

### 真实发票适配
本次用真实报销数据（出差北京的打车/高铁/酒店发票，共 11 张）回归测试 extractor，
发现并修复了多个布局相关问题。现已验证支持以下真实发票格式：

| 发票类型 | 布局特征 | 测试用例 |
|---------|---------|---------|
| 滴滴/曹操/美团打车 | 购买方销售方同行（"购 名称：A 销 名称：B"） | `test_real_buyer_seller_same_line` |
| 阳光出行等网约车 | 同上 | 同上 |
| 高铁电子客票 | 标准竖排，无明确销售方标签 | `test_real_train_ticket_no_explicit_seller` |
| 酒店发票（极端分散） | 发票号/日期/销售方都不在标签同行 | `test_real_scattered_layout_invoice_no_and_date` + `test_real_scattered_layout_seller_fallback` |

如果你遇到无法正确提取的发票格式，欢迎提 issue 附上脱敏文本片段。

### 变更
- `Category` 从 `str, Enum` 改为配置驱动的 `CategoryDef` dataclass
- `TOTAL_GROUPING`（市外交通合并到差旅）废除，每类 1:1 独立汇总
- `KEYWORDS` 字典从 `classifier.py` 模块级常量移到 `categories.py` 的 `DEFAULT_CATEGORIES`
- LLM 的 `SYSTEM_PROMPT` 改为根据当前类目动态生成
- 汇总 sheet 的类目列表从硬编码改为从配置动态生成
- `main.py` 入口不变，但内部完全重构

## [0.1.0] - 2026-08-10

### 首次发布
- 拖拽 PDF 自动提取金额/发票号/销售方/日期
- 规则分类器（关键词字典）+ DeepSeek LLM 兜底（hybrid 模式）
- 4 类分类（市内交通/差旅/材料/其他）
- 按 session（日期）管理多组报销记录
- Excel 导出（明细 + 汇总）
- 单 exe 打包支持
