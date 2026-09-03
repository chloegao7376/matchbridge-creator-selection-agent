# retrieval、fit 与 recommendations 参数分层

页面和 OpenAPI 按三个业务阶段分开：

| 模块 | 主接口 | 职责 |
|---|---|---|
| `retrieval` | `GET /api/retrieval/hybrid` | SQL 硬条件后，执行关键词与内容相似度混合召回 |
| `fit` | `POST /api/fit/calculate` | 对 Hybrid 召回候选达人进行业务适配度计算 |
| `recommendations` | `POST /api/recommendations/ranked` | 综合 Hybrid 召回、fit 与风险决策，输出最终推荐 |

旧的 `GET /api/recommendations/features` 仅作特征明细审计和调试，已归入 `internal-audit` 并标记为 deprecated，不再作为 fit 业务模块。

## 页面分层

业务人员默认看到：

    Campaign
    query
    候选人数

“召回高级设置”默认折叠：

    keyword_weight
    vector_weight
    retrieval_depth
    RRF排名平滑参数

`fit` 作为独立模块展示七个维度。fit 设置只有：

    default  使用系统默认参数
    custom   展开并允许编辑完整七维权重

置信度、缺失值和风险规则不属于请求中的可编辑字段。

## fit 默认权重

| 维度 | 默认权重 |
|---|---:|
| 内容相关性 `content_relevance` | 30% |
| 受众适配度 `audience_fit` | 20% |
| 历史效果 `performance` | 15% |
| 成本效率 `cost_efficiency` | 10% |
| 流量质量 `traffic_quality` | 10% |
| 履约能力 `delivery_reliability` | 10% |
| 数据质量 `data_quality` | 5% |

这七个默认权重只在选择 `custom` 后开放编辑；选择 `default` 时由系统直接使用上表配置。

Swagger 的 `fit` 请求体提供 `default` 和 `custom` 两个命名示例，可从示例下拉选择后执行。Swagger 是 API 调试界面，不支持根据 `mode` 动态展开或禁用表单控件；这种交互需在业务前端实现。

fit 使用 `POST` 是因为调用会执行新的计算并写入运行、特征与评分快照，而不是只读取已有资源；七维权重也使用 JSON 请求体传递。如后续需要按 `recommendation_run_id` 读取已有结果，应另行提供 `GET` 查询接口。

## recommendations 默认请求

    {
      "campaign_id": "cmp_0001",
      "query": "配料表",
      "candidate_count": 50,
      "retrieval_advanced": {
        "keyword_weight": 0.5,
        "vector_weight": 0.5,
        "retrieval_depth": 100,
        "rrf_k": 60
      },
      "fit": {
        "mode": "default"
      }
    }

retrieval_advanced和fit均有默认值，因此最简请求只需：

    {
      "campaign_id": "cmp_0001",
      "query": "配料表",
      "candidate_count": 50
    }

## 自定义 fit 权重

    {
      "campaign_id": "cmp_0001",
      "query": "配料表",
      "candidate_count": 50,
      "fit": {
        "mode": "custom",
        "weights": {
          "content_relevance": 0.40,
          "audience_fit": 0.20,
          "performance": 0.10,
          "cost_efficiency": 0.10,
          "traffic_quality": 0.05,
          "delivery_reliability": 0.10,
          "data_quality": 0.05
        }
      }
    }

自定义时必须提交全部七个维度，且合计严格为1。default模式不得提交weights。页面应只在用户选择custom后展开权重控件，并实时显示合计。

retrieval_depth必须大于或等于candidate_count，避免界面输入值与实际执行值不一致。关键词权重和内容相似度权重不能同时为0。

## 固定策略

以下规则由系统固定管理：

- 低置信度得分向中性先验0.5收缩；
- 缺失维度重归一化并施加特征覆盖率惩罚；
- 有效BLOCK在硬过滤阶段排除；
- REVIEW位于PASS之后；
- 风险不计入fit_score。

`recommendations` 中的最终排名不等于单独的 `fit_rank`：候选人先经 Hybrid 召回进入候选池，再按七维生成 `fit_score`，最后应用风险决策。当前规则为 `PASS` 先于 `REVIEW`，同一风险决策内按 `fit_score` 降序。有效 `BLOCK` 在 SQL 硬过滤阶段已被排除，不会进入最终推荐。

## 审计

每次运行在recommendation_runs中保存retrieval_config和fit_config。

默认模式保存实际生效的默认权重；自定义模式保存七维权重及由权重内容生成的配置版本，例如fit_custom_v1_04f9ba54b1。特征和评分明细继续写入candidate_feature_snapshots和candidate_score_snapshots。
