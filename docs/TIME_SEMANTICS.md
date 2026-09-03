# 推荐运行时间与Campaign时间语义

每次Campaign硬过滤或带Campaign的关键词检索都会创建一条`recommendation_runs`记录，并固定UTC时间：

```text
run_id
campaign_id
run_type
started_at
evaluated_at
data_cutoff_at
completed_at
status
filter_policy_version
risk_policy_version
keyword_weight_config
query_text
```

## 判断时钟

| 判断事项 | 使用时间 |
|---|---|
| 账号当前状态 | `recommendation_run.evaluated_at` |
| 报价有效期 | `recommendation_run.evaluated_at` |
| BLOCK是否有效 | `recommendation_run.evaluated_at` |
| 数据截止点 | `recommendation_run.data_cutoff_at` |
| 竞品合作冷却窗口 | `campaign_brief.campaign_start_at` |
| 历史合同排他期 | `campaign_brief.campaign_start_at` |
| Brief创建时间 | 仅审计，不参与上述业务判断 |

当前底层报价和风险数据使用`date`字段，因此运行时间在SQL比较时转换为UTC日期；Recommendation Run本身保存带时区的完整时间戳。

## BLOCK规则

```text
decision = BLOCK
AND observed_at <= evaluated_at日期
AND (expires_at为空 OR expires_at >= evaluated_at日期)
```

## 竞品合作规则

```text
competitor_conflict =
    collaboration.brand_name属于Brief竞品列表
    AND (
        collaboration.ended_at
            >= campaign_start_at - competitor_exclusion_days
        OR
        collaboration.exclusive_until >= campaign_start_at
    )
```

API响应中的`recommendation_run_id`和`evaluated_at`可用于定位和复现某次结果。

