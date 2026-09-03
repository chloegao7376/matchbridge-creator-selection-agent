# 预算组合优化 v3

## 位置与输出

POST /api/recommendations/ranked 在 Hybrid 召回、七维 fit 评分和风险决策后运行预算组合优化，结果位于响应顶层的 budget_optimization。

主要输出包括：

- Brief 总预算和目标达人数；
- 入选达人、各自估算报价和 fit_score；
- 组合总成本、剩余预算和预算利用率；
- 组合预期主KPI、受众重叠代理惩罚与惩罚后的目标值；
- FULL / PARTIAL / EMPTY 人数完成状态和可执行提示。

## v3 目标与约束

加入候选人两两受众相似度后，目标函数变成集合相关的二次优化。v3 使用确定性 Beam Search 返回高质量可行解，并将 solution_status 标记为 HEURISTIC，不宣称全局最优：

```text
maximize
  sum(
    selected_i
    * baseline_primary_kpi_i
    * campaign_transfer_factor_i
    * confidence_factor_i
  )
  - audience_overlap_penalty(S)

subject to
  sum(selected_i * estimated_cost_i) <= total_budget_cny
  sum(selected_i) <= creator_count
  selected_i in {0, 1}
  risk_decision_i == PASS
  estimated_cost_i is valid
  baseline_primary_kpi_i is available
```

主 KPI 由 Brief 决定：awareness 对应 impressions，engagement 对应 engagements，conversion 对应 conversions。

```text
baseline_primary_kpi
  = 30日中位播放 × 交付数
  × 同品类历史KPI/播放收缩率

expected_primary_kpi
  = baseline_primary_kpi
  × campaign_transfer_factor
  × confidence_factor
```

Campaign迁移系数为：

```text
campaign_transfer_factor
  = 内容相关性 × 50%
  + 受众适配度 × 35%
  + 流量质量 × 10%
  + 履约能力 × 5%
```

置信因子沿用保守折损：

```text
confidence_factor
  = 0.7 + 0.3 × min(KPI预测置信度, overall_feature_confidence)
```

达人自身的同品类历史 KPI 率向全体同品类先验收缩，降低小样本极端值。成本不进入效用计算，只作为总预算硬约束，从而避免重复奖励低价。

## Audience overlap代理指标

两位候选人的受众相似度定义为：

```text
audience_similarity(i,j)
  = 年龄分布重叠 × 35%
  + 地区分布重叠 × 30%
  + 兴趣标签Jaccard相似度 × 20%
  + 性别分布重叠 × 15%
```

年龄、地区和性别使用分布重叠系数 sum(min(p_i[k], p_j[k]))；兴趣标签使用交集数除以并集数。各项及总分范围均为 0～1。

组合惩罚定义为：

```text
audience_overlap_penalty(S)
  = sum(
      audience_similarity(i,j)
      × min(expected_primary_kpi_i, expected_primary_kpi_j)
    )
    / max(creator_count - 1, 1)
```

该归一化使惩罚与主KPI保持相同单位，并限制其随组合人数增长的速度。每位入选达人返回其组合内平均受众相似度与分摊的重叠惩罚。

audience_overlap 是基于受众分布的代理估计，不是真实粉丝去重结果。获得平台侧去重触达数据后，应替换为真正的边际KPI模型。缺失某一分布时，该相似度分项暂用 0.5 中性代理并返回 warning。

当 overlap-adjusted KPI 相同时，依次优先原始预期主KPI总量、fit总分、更低总成本和更靠前的候选排名。REVIEW 候选不会被自动入选；有效 BLOCK 在更早的 SQL 硬过滤阶段已被排除。

## 当前边界

- 分布相似度只能描述受众结构相近，不能证明两位达人拥有相同粉丝；
- 历史相关性不代表真实投放的因果增量；
- conversion 目前最大化转化量，因缺少毛利和客单价口径，不宣称最大化利润；
- 平台、量级和内容角度的组合多样性尚未作为约束。

后续有真实 Campaign 成效、受众去重和商品利润数据后，再升级为真正的预估边际业务价值。

## 审计

每次运行的方法、目标、约束、入选名单、代理重叠指标和预算结果保存在 recommendation_runs.budget_config。估算报价来自当次特征快照，最终签约前仍需人工确认报价、权益、税费和可用档期。
