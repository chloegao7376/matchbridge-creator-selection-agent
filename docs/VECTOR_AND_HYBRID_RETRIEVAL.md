# Embedding、向量检索与混合召回

## 当前实现边界

当前 Provider 是 `local_hashing_char_ngram_v1`：它将中文字符 1/2/3-gram 稳定映射到 1536 维并归一化，不依赖外部 API，适合验证向量数据管道、pgvector 查询和融合逻辑。它不是训练语义模型，对无字面重叠的语义改写泛化较弱。

Provider 通过 `app/embedding/` 抽象，后续可替换为线上或本地训练模型；但文档向量与查询向量必须使用同一模型和维度。

## 生成向量

```bash
python -m app.db.init_db
python scripts/generate_embeddings.py
```

生成脚本保存 `embedding_model`、检索文档 SHA-256 和生成时间。文档和模型未变时会跳过；需要强制重算时使用 `--force`。数据库使用 `vector_cosine_ops` 的部分 HNSW 索引，仅索引非空向量。

## API

两个接口都必须传 `campaign_id`，执行顺序是：

1. 以本次推荐运行时间进行账号、报价和 BLOCK 等硬过滤。
2. 以 Campaign 开始时间判断竞品冷却窗口和历史排他期。
3. 仅在合格账号 ID 集合内做向量或混合召回。

```text
GET /api/retrieval/vector?campaign_id=cmp_0001&query=成分&limit=20
GET /api/retrieval/hybrid?campaign_id=cmp_0001&query=成分&limit=20
```

向量查询文本由 Campaign 品类、必选主题、调性、用户焦点词及其品类内同义词组成。查询仅检索与当前 Provider 的 `embedding_model` 一致的向量，使用 cosine distance 升序排列，同时返回 `vector_score = 1 - distance`。

## 混合融合

默认召回深度为 100，关键词和向量各占 50%，使用加权 Reciprocal Rank Fusion：

```text
raw_rrf = keyword_weight / (k + keyword_rank)
        + vector_weight  / (k + vector_rank)
```

默认 `k=60`，API 返回归一化的 `rrf_score`、两路原始 rank/score 及证据。关键词支路内部仍使用 `Campaign基础相关性×40% + 用户焦点词相关性×60%`。RRF 融合排名而非直接相加两种不同标度的分数。

## Warning 分层

| 层级 | 字段 | 含义 |
|---|---|---|
| 查询/Campaign级 | 响应顶层 `warnings` | 例如用户 query 与 Campaign 品类可能不一致，整次运行只返回一次 |
| 候选匹配级 | 每位候选人 `match_warnings` | 例如该达人只命中 Campaign 基础上下文，未发现 query 或品类内同义词的直接文本证据 |
| 达人风险级 | 每位候选人 `risk_warnings` | 本次运行时点仍有效且未标记为误报的 `REVIEW` 风险线索 |

`risk_warnings` 是需要人工复核的线索，不构成违规或事实认定。当前有效的 `BLOCK` 事件仍在 SQL 硬过滤阶段直接排除，不会作为可推荐候选人的普通提示返回。
