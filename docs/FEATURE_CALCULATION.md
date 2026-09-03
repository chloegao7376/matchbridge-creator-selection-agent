# Hybrid Top-K 候选特征计算（内部审计）

## Top 50 的含义

Hybrid Top 50 是关键词和向量经 RRF 融合后的前 50 个召回候选，不是最终适配度前 50。它的作用是把计算较重的受众、效果、成本、履约特征限制在较小候选池内。当 SQL 硬过滤合格池小于 50 时，对全部合格候选计算。

## 业务 API

fit 业务模块使用：

```text
POST /api/fit/calculate
```

该接口对 Hybrid 候选计算七维 `fit_score`，并按 `fit_rank` 返回。默认权重为内容相关性 30%、受众适配度 20%、历史效果 15%、成本效率 10%、流量质量 10%、履约能力 10%、数据质量 5%。

## 旧版审计 API

```text
GET /api/recommendations/features
    ?campaign_id=cmp_0001
    &query=成分
    &top_k=50
    &retrieval_depth=100
```

该接口已标记 deprecated，并归入 `internal-audit`。返回顺序仍是 Hybrid 召回顺序；它只保留分项特征明细，不生成最终 `fit_score`，也不按特征重新排序。

## 特征维度

| 维度 | v1 特征 |
|---|---|
| `content_relevance` | 关键词相关性、向量余弦相似度 |
| `audience_fit` | 目标性别、年龄段、兴趣、目标地区受众覆盖 |
| `performance` | 30日互动率、中位播放/粉丝、历史ROI |
| `cost_efficiency` | 含代理费和交付数的估算成本、单人预算余量、估算CPM |
| `traffic_quality` | 活跃粉丝、可疑账号观测、重复评论、播放稳定性 |
| `delivery_reliability` | 历史准时交付率、平均修改次数 |
| `data_quality` | 账号置信度、快照新鲜度、受众样本量 |

每个特征保留 `score`、`raw_value`、`data_source`、`as_of`、`confidence`、`missing` 和 `evidence`。缺失特征不默认填充 0.5；维度内聚合会对可用特征重新归一化权重。

## 地区特征

- `audience_region_coverage` 是目标地区在粉丝地区分布中的已观测占比，v1 在受众维度中只占 10%。
- `creator_location_match` 保留达人常驻地是否命中目标地区，但当前 Brief 没有“必须到店/到场”语义，因此不计入受众得分。
- 品牌总部所在地不参与计算。

## 审计与时间

每次计算创建 `feature_calculation` 类型的 Recommendation Run，数据快照只使用 `snapshot_date <= evaluated_at`的最新记录。结果以 `candidate_features_v1` 版本写入 `candidate_feature_snapshots`，可通过 `recommendation_run_id` 复现和审计。

## 当前边界

- 当前向量特征仍来自本地哈希 Embedding 基线，置信度标记为 0.55。
- CPM 先保留原始值，尚未按平台、量级和候选池分位数归一化，因此暂不计入成本维度得分。
- 流量质量为观测性信号，不构成作弊事实认定。
- 七维 fit 权重、风险决策聚合与 v1 组合预算优化已实现。
- v3 预算目标最大化受众重叠代理修正后的 `expected_primary_kpi`；该代理不是真实粉丝去重，因果增量仍未建模。
