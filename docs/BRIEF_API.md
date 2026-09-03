# Campaign Brief CRUD与第一版硬条件过滤

启动服务：

```bash
source .venv/bin/activate
uvicorn app.main:app --reload
```

交互式文档位于 <http://127.0.0.1:8000/docs>。

## API列表

| 方法 | 路径 | 用途 |
|---|---|---|
| `POST` | `/api/briefs` | 创建Brief |
| `GET` | `/api/briefs` | 分页列出Brief |
| `GET` | `/api/briefs/{campaign_id}` | 获取单个Brief |
| `PATCH` | `/api/briefs/{campaign_id}` | 局部更新Brief |
| `DELETE` | `/api/briefs/{campaign_id}` | 删除Brief |
| `GET` | `/api/briefs/{campaign_id}/eligibility` | 执行SQL硬条件过滤 |

## 创建Brief

```bash
curl -X POST http://127.0.0.1:8000/api/briefs \
  -H 'Content-Type: application/json' \
  -d '{
    "brand_name": "澄光护肤",
    "product_name": "舒缓精华新品",
    "product_category": "美妆个护",
    "campaign_objective": "engagement",
    "primary_kpi": "engagements",
    "target_platforms": ["小红书", "抖音"],
    "target_regions": ["上海", "杭州"],
    "target_audience": {
      "gender_preference": "female",
      "primary_age_band": "25_34",
      "interest_tags": ["品质生活", "健康"]
    },
    "tone_tags": ["知性温柔"],
    "required_topics": ["成分", "敏感肌"],
    "forbidden_topics": ["夸大承诺"],
    "content_formats": ["图文", "短视频"],
    "deliverables_per_creator": 1,
    "campaign_start_at": "2026-10-01",
    "campaign_end_at": "2026-10-31",
    "total_budget_cny": 150000,
    "max_budget_per_creator_cny": 30000,
    "creator_count": 5,
    "preferred_creator_tiers": ["micro", "mid"],
    "competitor_brands": ["微澜美研"],
    "competitor_exclusion_days": 60,
    "usage_rights_days": 30,
    "exclusivity_required_days": 14,
    "risk_tolerance": "low",
    "brief_text": "为国货美妆新品选择小红书和抖音达人。"
  }'
```

Pydantic会拒绝以下情况：

- 结束日期早于开始日期。
- 单人预算超过总预算。
- 内容形式不受所选平台支持。
- 平台、受众、内容形式等必要列表为空。
- 出现未声明字段。

## 局部更新

```bash
curl -X PATCH http://127.0.0.1:8000/api/briefs/{campaign_id} \
  -H 'Content-Type: application/json' \
  -d '{"total_budget_cny": 180000}'
```

更新时会将新字段和原Brief合并后重新执行全部交叉校验。

## 执行硬条件过滤

只返回合格账号，最多返回100个：

```bash
curl 'http://127.0.0.1:8000/api/briefs/{campaign_id}/eligibility?limit=100'
```

同时查看合格和被排除账号及其理由：

```bash
curl 'http://127.0.0.1:8000/api/briefs/{campaign_id}/eligibility?include_excluded=true&limit=500'
```

第一版硬条件全部由SQL判断：

1. 账号状态必须为`active`。
2. 账号平台必须属于Brief目标平台。
3. 达人类目标签必须包含产品类目。
4. 必须存在当前有效且内容形式兼容的报价。
5. 兼容报价不得超过单人预算。
6. 不得存在仍有效的`BLOCK`风险事件。
7. 不得命中竞品合作回看窗口或仍有效的历史排他期。

可能的淘汰理由：

```text
account_inactive
platform_mismatch
category_mismatch
no_compatible_rate_card
over_per_creator_budget
active_block_risk
competitor_exclusion_conflict
```

`REVIEW`风险不会在这一层淘汰账号，后续由独立风险审核模块处理。

硬过滤响应会返回`recommendation_run_id`和带时区的`evaluated_at`。账号状态、报价和BLOCK均按本次运行时间判断，不再使用Brief创建日。完整时间规则见[`TIME_SEMANTICS.md`](TIME_SEMANTICS.md)。
