"""extractor 字段提取测试，使用合成发票文本片段。"""

from __future__ import annotations

from src.core.extractor import extract_fields

SAMPLE_INVOICE_TEXT = """
                         增值税电子普通发票
                              (发票联)

发票代码: 011002200111
发票号码: 24412000000000012345
开票日期: 2026年08月10日

购买方名称: 浙江大学
购买方纳税人识别号: 123456789012345XXX

货物或应税劳务名称        规格型号   单位   数量   单价       金额
   住宿费                                                   350.00
                                                            税额 21.00

销售方名称: 杭州西湖宾馆管理有限公司
销售方纳税人识别号: 91XXXXXXXXXXXXXXX

价税合计（大写） ⊙叁佰伍拾元整
              （小写） ￥350.00
"""


def test_extract_amount_from_full_text():
    fields = extract_fields(SAMPLE_INVOICE_TEXT)
    assert fields.amount is not None
    assert abs(fields.amount - 350.00) < 0.01


def test_extract_invoice_no():
    fields = extract_fields(SAMPLE_INVOICE_TEXT)
    assert fields.invoice_no == "24412000000000012345"


def test_extract_issue_date_normalized():
    """'2026年08月10日' 归一化为 '2026-08-10'。"""
    fields = extract_fields(SAMPLE_INVOICE_TEXT)
    assert fields.issue_date == "2026-08-10"


def test_extract_seller_name():
    fields = extract_fields(SAMPLE_INVOICE_TEXT)
    assert fields.seller_name == "杭州西湖宾馆管理有限公司"


def test_empty_text():
    fields = extract_fields("")
    assert fields.amount is None
    assert fields.invoice_no is None


def test_partial_fields_only():
    """只有金额，没有发票号/日期/销售方的情况。"""
    text = "随便一段文字 价税合计（小写） ￥100.00"
    fields = extract_fields(text)
    assert fields.amount == 100.00
    assert fields.invoice_no is None
    assert fields.issue_date is None
    assert fields.seller_name is None


def test_date_with_dashes():
    """'2026-08-10' 格式。"""
    text = "开票日期: 2026-08-10\n价税合计（小写） ￥10.00"
    fields = extract_fields(text)
    assert fields.issue_date == "2026-08-10"


def test_date_with_slashes():
    text = "开票日期 2026/8/10\n价税合计（小写） ￥10.00"
    fields = extract_fields(text)
    assert fields.issue_date == "2026-08-10"


def test_extract_8_digit_invoice_no():
    """老式 8 位发票号也能提取（修原 #13）。"""
    text = "发票号码: 12345678\n价税合计（小写） ￥10.00"
    fields = extract_fields(text)
    assert fields.invoice_no == "12345678"


def test_extract_10_digit_invoice_no():
    """10 位发票号。"""
    text = "发票号码: 1234567890\n价税合计（小写） ￥10.00"
    fields = extract_fields(text)
    assert fields.invoice_no == "1234567890"


def test_date_chinese_colon_no_space():
    """'开票日期：2026年...'（中文冒号无空格）也能匹配（修原 #13）。"""
    text = "开票日期：2026年08月10日\n价税合计（小写） ￥10.00"
    fields = extract_fields(text)
    assert fields.issue_date == "2026-08-10"


def test_seller_name_crlf_stripped():
    """Windows CRLF 下销售方名称不应带 \r（修原 #13）。"""
    text = "销售方名称: 某公司\r\n价税合计（小写） ￥10.00"
    fields = extract_fields(text)
    assert fields.seller_name == "某公司"
    assert "\r" not in (fields.seller_name or "")


# ---------- 真实发票布局测试（来自真实样本，脱敏）----------


def test_real_buyer_seller_same_line():
    """真实打车发票：购买方销售方在同一行，不能误匹配购买方。

    布局：'购 名称：XX大学 销 名称：XX科技有限公司'
    """
    text = """电子发票（普通发票）
发票号码： 26327000001413099458
开票日期： 2026年08月06日
购 名称：某大学 销 名称：苏州市吉利优行电子科技有限公司
买 售
价税合计（大写） 伍拾壹圆贰角贰分 （小写）¥51.22"""
    fields = extract_fields(text)
    assert fields.seller_name == "苏州市吉利优行电子科技有限公司"
    assert fields.seller_name != "某大学"
    assert "某大学" not in (fields.seller_name or "")


def test_real_scattered_layout_invoice_no_and_date():
    """真实酒店发票：发票号和日期跨行，不在标签后面。

    布局：'发票号码：\\n...\\n制 26112000003231988456\\n...\\n国家税务总局 2026年08月04日'
    """
    text = """电子发票（普通发票）
发票号码：
开票日期：
下载次数：1
国
统一发票监
制 26112000003231988456
全 章
国家税务总局 2026年08月04日
北 京市税务局
某大学 北京华邮国鼎酒店管理有限公司
12100000470095016Q 91110106MA00CRC104
价税合计（大写） 肆佰捌拾肆圆整 （小写） ¥ 484.00"""
    fields = extract_fields(text)
    assert fields.invoice_no == "26112000003231988456"
    assert fields.issue_date == "2026-08-04"


def test_real_scattered_layout_seller_fallback():
    """真实酒店发票：销售方名称也不在标签后，靠公司特征词兜底。

    布局：'某大学 北京华邮国鼎酒店管理有限公司'（购买方销售方同行，无标签）
    """
    text = """电子发票（普通发票）
发票号码：26112000003275240161
开票日期：2026年08月06日
某大学 北京鲲翔源酒店管理服务有限公司
价税合计（大写） 壹仟贰佰玖拾叁圆整 （小写） ¥ 1293.00"""
    fields = extract_fields(text)
    assert fields.seller_name == "北京鲲翔源酒店管理服务有限公司"
    assert "某大学" not in (fields.seller_name or "")


def test_real_train_ticket_no_explicit_seller():
    """真实高铁票：无明确销售方标签，不应强行猜测。

    高铁票文本里没有"销售方名称"字样，也没有"XX有限公司"格式，
    应返回 None 或不包含购买方名（不误提取"某大学"）。
    """
    text = """电子发票（铁路电子客票）
发票号码:26339166279001584016 开票日期:2026年08月06日
杭州西 G50 北京南
￥568.00
票价:
购买方名称:某大学 统一社会信用代码:12100000470095016Q
中国铁路祝您旅途愉快"""
    fields = extract_fields(text)
    assert fields.invoice_no == "26339166279001584016"
    assert fields.issue_date == "2026-08-06"
    assert fields.seller_name is None or "某大学" not in (fields.seller_name or "")
