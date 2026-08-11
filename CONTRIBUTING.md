# 贡献指南

感谢你对 FapiaoFlow 的兴趣！这是一个面向需要批量整理电子发票场景的开源工具，任何贡献都欢迎。

## 🐛 报告 Bug / 提建议

- 先在 [Issues](https://github.com/songzaiyang7-maker/FapiaoFlow/issues) 搜索是否已有相同问题
- 新建 issue 时请描述：操作系统、复现步骤、期望行为、实际行为
- 如果是分类不准，请附上**脱敏后的发票文本片段**（销售方名称、货物名称、金额即可，不要附完整 PDF）

## 🔒 安全问题

**不要在公开 issue 里报告安全漏洞。** 详见 [SECURITY.md](SECURITY.md)。

## 💻 本地开发

```bash
git clone https://github.com/songzaiyang7-maker/FapiaoFlow.git
cd FapiaoFlow
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux
pip install -e ".[dev]"         # 安装开发依赖（pytest/ruff 等）
pytest                          # 跑测试
ruff check .                    # lint
python main.py                  # 启动应用
```

## 📝 代码规范

- 用 `ruff check .` 检查代码风格（配置在 `pyproject.toml`）
- 新增功能请补测试（`tests/` 目录，文件名 `test_*.py`）
- 提交前确保 `pytest` 全绿
- core 层（`src/core/`）不依赖 GUI，应可独立测试

## 🏷️ 分类关键词贡献

最常见也最有用的贡献：补充分类关键词。

关键词定义在 `data/categories.json`（首次运行后生成），或在应用内「设置 → 类目管理」编辑。如果你发现某类发票分类不准，欢迎：

1. 在 issue 里描述：发票销售方名称、货物名称、期望归到哪类
2. 或直接提 PR 修改默认关键词（`src/core/categories.py` 的 `DEFAULT_CATEGORIES`）

## 🔄 提交 PR 的流程

1. Fork 仓库，新建分支（`git checkout -b feature/xxx`）
2. 写代码 + 测试
3. `pytest` 和 `ruff check .` 都通过
4. 提交（commit message 用中文或英文均可，说清楚改了什么）
5. 发 PR，描述改动内容和动机

## 📋 项目结构

详见 README 的「后端架构」章节。简单说：

- `src/core/` —— 核心逻辑（解析、分类、持久化、导出），无 GUI 依赖
- `src/gui/` —— PyQt6 界面
- `src/utils/` —— 工具函数
- `tests/` —— 测试

## 💡 好的首次贡献

如果不知道从哪开始，可以：

- 补充测试覆盖（`storage.py` / `exporter.py` / GUI 层目前覆盖较少）
- 改进文档（错别字、表述不清的地方）
- 补充关键词字典（你的真实发票里有哪些没被正确分类的？）
- 翻译 README（英文版）
