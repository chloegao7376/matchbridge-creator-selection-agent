from __future__ import annotations

CATEGORY_SYNONYMS: dict[str, dict[str, list[str]]] = {
    "食品饮料": {
        "成分": ["配料表", "原料", "配方", "营养成分"],
        "配料表": ["成分", "原料", "配方", "营养成分"],
        "低糖": ["减糖", "控糖", "无糖"],
        "探店": ["餐厅体验", "门店体验", "到店测评"],
        "咖啡": ["咖啡豆", "手冲", "拿铁"],
    },
    "美妆个护": {
        "成分": ["配方", "原料", "成分党"],
        "敏感肌": ["敏感皮", "舒缓", "低刺激", "维稳"],
        "护肤": ["护肤品", "皮肤护理", "保养"],
        "美白": ["提亮", "淡斑", "焕亮"],
        "防晒": ["防晒霜", "防晒乳", "防紫外线"],
    },
    "时尚穿搭": {
        "穿搭": ["搭配", "造型", "服饰搭配"],
        "轻奢": ["轻奢风", "高质感", "品质穿搭"],
        "面料": ["材质", "织物", "布料"],
    },
    "科技数码": {
        "续航": ["电池", "电量", "充电"],
        "影像": ["拍照", "摄影性能", "摄像"],
        "性能": ["跑分", "处理器", "流畅度"],
    },
    "母婴育儿": {
        "辅食": ["宝宝餐", "婴幼儿食品", "儿童餐"],
        "早教": ["启蒙", "亲子教育", "幼儿教育"],
        "安全": ["母婴安全", "儿童安全", "安全材质"],
    },
    "健身运动": {
        "跑步": ["跑者", "慢跑", "路跑"],
        "力量训练": ["举铁", "抗阻训练", "肌肉训练"],
        "恢复": ["运动恢复", "拉伸", "放松"],
    },
    "家居生活": {
        "收纳": ["整理", "空间整理", "储物"],
        "清洁": ["家务", "去污", "清洁用品"],
        "软装": ["家居布置", "室内搭配", "家装风格"],
    },
    "旅行摄影": {
        "攻略": ["旅行指南", "路线", "行程"],
        "酒店": ["住宿", "民宿", "酒店测评"],
        "构图": ["摄影构图", "取景", "画面设计"],
    },
}


def expand_terms(terms: list[str], campaign_category: str | None = None) -> dict[str, list[str]]:
    category_map = CATEGORY_SYNONYMS.get(campaign_category or "", {})
    expansions: dict[str, list[str]] = {}
    for term in terms:
        normalized = term.strip().lower()
        if not normalized:
            continue
        synonyms = category_map.get(normalized, [])
        expansions[normalized] = list(dict.fromkeys([normalized, *(synonym.lower() for synonym in synonyms)]))
    return expansions

