"""生成合成发票 PDF，用于截图演示和测试。

运行：
    python scripts/generate_sample_invoices.py [输出目录]

默认输出到 ./sample_invoices/。生成的 PDF 覆盖各种真实发票布局，
拖入 FapiaoFlow 后能呈现：
- 自动分类成功（差旅/材料，绿行/白行）
- 待复核（市内交通，黄行）
- 手动归类（用户拖到指定类目，绿行）
- 解析失败（非发票 PDF，红行）

所有数据均为虚构，不含任何真实信息。
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas


def _make_pdf_bytes(lines: list[str]) -> bytes:
    """生成包含给定文本行的 PDF（中文用 STSong-Light CID 字体）。"""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    try:
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        c.setFont("STSong-Light", 10)
    except Exception:
        c.setFont("Helvetica", 10)
    y = 800
    for line in lines:
        c.drawString(50, y, line)
        y -= 14
    c.showPage()
    c.save()
    return buf.getvalue()


# 合成发票样本：覆盖真实发票的各种布局和分类场景
# 命名规律：类型_预期分类_备注.pdf
SAMPLES: list[tuple[str, list[str]]] = [
    # === 差旅类（自动分类成功，confidence 高）===
    (
        "高铁票_杭州到上海_差旅.pdf",
        [
            "电子发票（铁路电子客票）",
            "发票号码:26339166279001584016 开票日期:2026年08月15日",
            "浙江省税务局",
            "杭州东 G7371 上海虹桥",
            "Hangzhoudong Shanghaihongqiao",
            "2026年08月15日 09:32开 03车12A号 二等座",
            "￥146.50",
            "票价:",
            "购买方名称:某科技有限公司 统一社会信用代码:91330100MA2ABC123X",
            "中国铁路祝您旅途愉快",
        ],
    ),
    (
        "酒店住宿_出差_差旅.pdf",
        [
            "增值税电子普通发票",
            "发票号码:24412000000000012345",
            "开票日期:2026年08月15日",
            "销售方名称:上海某商务酒店管理有限公司",
            "销售方纳税人识别号:91310101123456789X",
            "项目名称        金额        税率        税额",
            "*住宿费         456.60      6%          27.40",
            "价税合计（大写） 肆佰捌拾肆圆整",
            "              （小写） ￥484.00",
        ],
    ),
    (
        "机票_北京出差_差旅.pdf",
        [
            "增值税电子普通发票",
            "发票号码:24412000000000067890",
            "开票日期:2026年08月14日",
            "销售方名称:中国某航空股份有限公司",
            "货物名称:航空运输服务",
            "行程:杭州 - 北京",
            "价税合计（大写） 壹仟贰佰叁拾元整",
            "（小写） ￥1230.00",
        ],
    ),
    # === 材料类（自动分类成功）===
    (
        "实验试剂采购_材料.pdf",
        [
            "增值税电子普通发票",
            "发票号码:24412000000000033333",
            "开票日期:2026年08月12日",
            "销售方名称:杭州某化学试剂有限公司",
            "货物名称:实验试剂 玻璃仪器",
            "价税合计（大写） 伍佰陆拾柒圆整",
            "（小写） ￥567.00",
        ],
    ),
    (
        "办公耗材_材料.pdf",
        [
            "增值税电子普通发票",
            "发票号码:24412000000000044444",
            "开票日期:2026年08月10日",
            "销售方名称:某办公用品商贸有限公司",
            "货物名称:打印机 文具 耗材",
            "价税合计（小写） ￥328.50",
        ],
    ),
    # === 市内交通类（自动分类，confidence 0.6，黄行待复核）===
    (
        "滴滴打车_市内_待复核.pdf",
        [
            "电子发票（普通发票）",
            "发票号码： 26327000001413099001",
            "开票日期： 2026年08月16日",
            "购 名称：某科技有限公司 销 名称：滴滴出行科技有限公司",
            "买 售",
            "方 方",
            "项目名称 单价 数量 金额 税率 税额",
            "*交通运输服务*网约车服务费 12.33 1 12.33 3% 0.37",
            "价税合计（大写） 壹拾贰圆柒角整 （小写）¥12.70",
        ],
    ),
    (
        "地铁出行_市内_待复核.pdf",
        [
            "增值税电子普通发票",
            "发票号码:24412000000000055555",
            "开票日期:2026年08月15日",
            "销售方名称:某市轨道交通集团有限公司",
            "货物名称:轨道交通 公交",
            "价税合计（小写） ￥45.00",
        ],
    ),
    # === 其他类（兜底，会显示待复核——这是正常行为，提示用户确认）===
    (
        "咨询服务费_其他.pdf",
        [
            "增值税电子普通发票",
            "发票号码:24412000000000066666",
            "开票日期:2026年08月08日",
            "销售方名称:某信息咨询服务中心",
            "货物名称:咨询服务",
            "价税合计（小写） ￥2000.00",
        ],
    ),
    # === 解析失败（红行：无价税合计）===
    (
        "非发票文档_解析失败.pdf",
        [
            "这是一份普通文档，不是发票。",
            "会议纪要",
            "时间：2026年8月10日",
            "参会人员：张三、李四、王五",
            "讨论了项目进度和下季度计划。",
            "（这里没有任何金额或价税合计字样）",
        ],
    ),
]


def main() -> int:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("sample_invoices")
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"生成 {len(SAMPLES)} 张合成发票 PDF 到 {out_dir}/")
    print()
    for name, lines in SAMPLES:
        path = out_dir / name
        path.write_bytes(_make_pdf_bytes(lines))
        print(f"  ✓ {name}")

    print()
    print("使用方法：")
    print("  1. 启动 FapiaoFlow（双击桌面 exe 或 python main.py）")
    print("  2. 把这些 PDF 拖入应用体验不同效果：")
    print("     - 拖到顶部「自动分类」区 → 程序智能判断类目")
    print("     - 拖到下方指定类目卡片 → 强制归到该类（绿行）")
    print("     - 「高铁/酒店/机票/试剂/耗材」会自动分类成功")
    print("     - 「滴滴/地铁」显示黄行（待复核）")
    print("     - 「非发票文档」显示红行（解析失败）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
