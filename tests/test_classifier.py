"""分类器单元测试。

类目改为配置驱动后，测试需要构造 list[CategoryDef] 传入。
"""

from __future__ import annotations

from src.core.categories import CategoryDef
from src.core.classifier import RuleClassifier, classify_invoice
from src.core.types import Invoice


def _default_categories() -> list[CategoryDef]:
    """与 DEFAULT_CATEGORIES 一致的测试用类目列表。"""
    return [
        CategoryDef(name="差旅", keywords=[
            "航空", "机票", "航班", "行程单", "机场", "民航",
            "铁路", "高铁", "火车", "动车", "车站", "客运",
            "酒店", "宾馆", "旅馆", "住宿", "民宿", "公寓", "招待所", "度假村", "饭店",
        ], color="#e3f2fd", priority=1),
        CategoryDef(name="材料", keywords=[
            "商贸", "办公", "书店", "材料", "实验室", "仪器",
            "试剂", "电脑", "打印机", "文具", "耗材", "图书", "玻璃仪器", "化学",
        ], color="#fff3e0", priority=2),
        CategoryDef(name="市内交通", keywords=[
            "出租", "网约车", "滴滴", "神州", "曹操出行", "公交", "地铁",
            "轨道交通", "共享单车", "停车", "哈啰", "美团打车",
        ], color="#e8f5e9", priority=3),
        CategoryDef(name="其他", keywords=[], color="#f3e5f5", priority=99),
    ]


def _make(text: str = "", seller: str | None = None) -> Invoice:
    return Invoice(
        file_path="x.pdf",
        file_name="x.pdf",
        raw_text=text,
        seller_name=seller,
    )


def test_hotel_goes_to_travel():
    """酒店发票 → 差旅（住宿并入差旅规则）。"""
    cats = _default_categories()
    inv = _make(text="住宿费", seller="杭州西湖宾馆")
    cat, conf, note = classify_invoice(inv, cats)
    assert cat == "差旅"
    assert conf >= 0.7
    assert "差旅" in note or "命中" in note


def test_train_ticket_goes_to_travel():
    cats = _default_categories()
    inv = _make(text="杭州东 → 北京南 高铁", seller="中国铁路")
    cat, conf, _ = classify_invoice(inv, cats)
    assert cat == "差旅"


def test_didi_defaults_to_local_transport():
    """滴滴发票默认归市内交通，confidence=0.6。"""
    cats = _default_categories()
    inv = _make(text="网约车", seller="滴滴出行科技有限公司")
    cat, conf, note = classify_invoice(inv, cats)
    assert cat == "市内交通"
    assert conf == 0.6
    assert "外地" in note or "手动" in note


def test_material_classification():
    cats = _default_categories()
    inv = _make(text="实验仪器采购", seller="杭州XX科技有限公司")
    cat, conf, _ = classify_invoice(inv, cats)
    assert cat == "材料"
    assert conf >= 0.7


def test_no_keywords_goes_to_other():
    cats = _default_categories()
    inv = _make(text="某段不含关键词的发票文本", seller="某某咨询服务部")
    cat, conf, _ = classify_invoice(inv, cats)
    assert cat == "其他"
    assert conf == 0.3


def test_empty_text_goes_to_other():
    cats = _default_categories()
    inv = _make(text="", seller=None)
    cat, conf, note = classify_invoice(inv, cats)
    assert cat == "其他"
    assert conf == 0.3
    assert "未提取" in note


def test_conflict_priority():
    """同时命中'酒店'和'出租'：差旅优先级(priority=1) < 市内交通(3)，归差旅。"""
    cats = _default_categories()
    inv = _make(text="酒店 出租", seller="某酒店")
    cat, conf, note = classify_invoice(inv, cats)
    assert cat == "差旅"
    assert conf <= 0.5  # 冲突时置信度降低
    assert "优先级" in note


def test_multiple_hits_increase_confidence():
    """命中多个关键词 → confidence 更高。"""
    cats = _default_categories()
    inv = _make(text="航空 机票 航班", seller="某航空公司")
    cat, conf, _ = classify_invoice(inv, cats)
    assert cat == "差旅"
    assert conf >= 0.9


def test_rule_classifier_protocol():
    """RuleClassifier 类应该和函数返回一致。"""
    cats = _default_categories()
    inv = _make(text="住宿", seller="某酒店")
    rc = RuleClassifier(cats)
    result1 = rc.classify(inv)
    result2 = classify_invoice(inv, cats)
    assert result1 == result2


def test_custom_category_works():
    """用户自定义类目也能正常分类。"""
    cats = [
        CategoryDef(name="餐饮", keywords=["餐", "饭", "食", "饮", "茶", "咖啡"], color="#fce4ec", priority=1),
        CategoryDef(name="其他", keywords=[], color="#f3e5f5", priority=99),
    ]
    inv = _make(text="餐饮服务", seller="某餐饮公司")
    cat, conf, _ = classify_invoice(inv, cats)
    assert cat == "餐饮"
    assert conf >= 0.7
