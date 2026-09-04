# 七维适配度评分与排序

## API

```text
GET /api/recommendations/ranked
    ?campaign_id=cmp_0001
    &query=成分
    &top_k=50
    &retrieval_depth=100
```

该接口执行 SQL 硬过滤、Hybrid Top-K、特征计算和最终评分。评分版本为 `fit_scoring_v2_history_tiering`。

默认业务响应按三阶段组织：

```text
stages.retrieval  Campaign+query的关键词/向量/RRF召回摘要
stages.fit        包含检索信号和业务特征的评分口径
stages.final      PASS/REVIEW与最终排序口径
```

响应顶层的 `budget_optimization` 进一步在 Brief 总预算和目标达人数内，从 PASS 候选中选出受众重叠代理修正后预期主 KPI 最大的达人组合。

每位候选人的默认业务展示包含身份字段、三个最终指标、证据化理由和业务注意事项：

```json
{
  "final_rank": 1,
  "fit_score": 72.83,
  "risk_decision": "PASS",
  "selected_in_budget_plan": true,
  "why_this_creator": {
    "dimension": "candidate_selection",
    "statement": "该达人以业务适配度72.8分进入推荐候选，当前风险审核结果为PASS；主要评分贡献为内容相关性21.4分、受众适配度15.2分。",
    "evidence_values": {
      "fit_score": 72.83,
      "risk_decision": "PASS"
    }
  },
  "why_in_final_combination": {
    "dimension": "portfolio_selection",
    "statement": "该达人进入最终组合：预计贡献转化94.73……计入完整重叠代理影响后，估算边际目标贡献约转化80.62，因此在预算约束下有助于提升组合目标。",
    "evidence_values": {
      "expected_primary_kpi": 94.7337,
      "full_overlap_impact_proxy": 14.109,
      "estimated_marginal_objective_contribution": 80.6247
    }
  },
  "recommendation_reasons": [
    {
      "dimension": "content_relevance",
      "statement": "内容相关性82.0分；近期内容命中：成分、配料表。",
      "evidence_values": {
        "content_relevance_score": 0.82,
        "matched_terms": ["成分", "配料表"]
      }
    }
  ],
  "business_notes": [
    "内容契合度为系统初筛结果，最终合作前需人工确认。",
    "当前金额为估算成本，最终以商务确认的报价、权益和税费为准。"
  ]
}
```

`why_this_creator` 回答该达人为何进入推荐候选，引用 `fit_score`、风险决策及贡献最高的评分维度。`selected_in_budget_plan` 表示是否被预算组合优化选中；只有值为 `true` 时才返回 `why_in_final_combination`，未入选者该字段为 `null`。

`why_in_final_combination` 回答该达人为何属于最终组合，引用预期主 KPI、Campaign 迁移系数、置信修正、报价占比、与其他入选达人的受众相似度，以及扣除完整受众重叠代理影响后的估算边际目标贡献。这里的受众重叠仍是代理估计，不代表平台真实粉丝去重结果。

`recommendation_reasons` 是由已保存的特征快照确定性生成，可包含内容相关性、主题命中、目标年龄段占比、互动率、ROI、准时交付率、估算成本和预算占比。数值同时保留在 `evidence_values`，避免只返回无法审计的定性文案。

`business_notes` 不暴露 Embedding、向量、RRF、索引或模型参数等技术用语。技术实现信息只保留在内部快照和审计数据中。

`fit_score` 已包含检索相关性：内容维度30%中，关键词相关性占60%、向量相似度占40%，即二者在总分中的名义权重分别为18%和12%。RRF 只用于确定进入精算的候选池，不再重复加入 `fit_score`。

## 七维权重

| 维度 | 权重 |
|---|---:|
| 内容相关性 `content_relevance` | 30% |
| 受众适配度 `audience_fit` | 20% |
| 历史效果 `performance` | 15% |
| 成本效率 `cost_efficiency` | 10% |
| 流量质量 `traffic_quality` | 10% |
| 履约能力 `delivery_reliability` | 10% |
| 数据质量 `data_quality` | 5% |

权重和为 1。当前是业务初始权重，后续应用离线相关性标签、实际Campaign效果和品牌反馈校准，不应在无版本变更的情况下直接修改。

### 历史有限：只重新分配被释放的历史效果权重

历史有限达人先按 `history_reliability` 保留历史效果权重：

```text
performance_effective = performance_base × history_reliability
released_weight = performance_base × (1 − history_reliability)
```

`released_weight` 再按内容相关性40%、受众适配度30%、流量质量20%、数据质量10%分配。
这四个比例是释放权重的分配比例，不是最终七维权重。成本效率与履约能力保持基础权重。

### 完全冷启动：固定稳定性信号权重

完全冷启动使用系统固定权重：内容相关性36%、受众适配度24%、历史效果0%、成本效率10%、
流量质量13%、履约能力10%、数据质量7%。缺失维度仍执行可用权重重归一化与覆盖率惩罚，
不会用虚构值补齐；主KPI预测使用低置信度品类基线代理。完全冷启动候选保留在推荐列表供
人工复核，但默认不进入预算组合，只有人工明确加入并锁定后才允许参与重新优化。

## 置信度处理

每个维度的置信度是其可计分特征置信度的平均值。低置信度得分向中性先验 0.5 收缩：

```text
confidence_adjusted_score
  = dimension_score * confidence
  + 0.5 * (1 - confidence)
```

这意味着低置信度的高分不会被当作确定性高分，低置信度的低分也不会被当作确定性负面结论。

## 缺失值处理

缺失维度不填 0，也不默认填 0.5。评分器对可用维度权重重新归一化，然后施加特征覆盖率惩罚：

```text
feature_coverage = 可用维度原始权重之和
coverage_factor = 0.7 + 0.3 * feature_coverage
fit_score = 可用维度归一化加权分 * coverage_factor * 100
```

例如仅缺少 10% 的履约维度时，`feature_coverage=0.9`，覆盖率系数为 0.97。这避免缺失数据候选人因权重重新归一化而反向获益。

## 内部两种排名

- `fit_rank`：仅按 `fit_score` 降序，表示纯业务适配度。
- `final_rank`（数据库内部字段为 `recommendation_rank`）：先排 `PASS`，再排 `REVIEW`，同一风险层内按 `fit_score` 降序。

风险不进入 `fit_score`。有效 `BLOCK` 在 SQL 硬过滤阶段已排除；存在有效 REVIEW 线索时，候选人保留其真实 `fit_rank`，但在 `recommendation_rank` 中位于 PASS 候选之后。当前 `risk_decision` 是基于已有有效风险事件的临时决策，不等同于尚未实现的完整内容审核引擎。

## 审计

默认业务 API 不展开以下内部字段，但数据库完整保留：

- 维度原始得分、置信度和置信调整得分；
- 各维度对最终分数的 `contribution_points`；
- `feature_coverage`、`overall_confidence` 和 `missing_dimensions`；
- 评分解释、完整特征和风险提示。

结果写入 `candidate_score_snapshots`，与 `candidate_feature_snapshots` 和 Recommendation Run 关联。
