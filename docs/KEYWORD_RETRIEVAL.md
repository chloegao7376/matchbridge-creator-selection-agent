# 达人检索文档与关键词召回

## 构建检索文档

数据库初始化会启用`pg_trgm`扩展并创建GIN Trigram索引。首次使用或内容数据更新后运行：

```bash
source .venv/bin/activate
python -m app.db.init_db
python scripts/build_search_documents.py
```

构建过程会为每个平台账号生成一份可审计检索文档，包含：

- 达人名称与简介
- 平台和主营类目
- 内容风格
- 近90天高频主题
- 最新受众兴趣
- 按播放量选择的5条代表内容

脚本使用账号ID Upsert，可重复执行。

## 关键词检索API

不带Campaign，搜索整个达人库：

```bash
curl --get 'http://127.0.0.1:8000/api/retrieval/keyword' \
  --data-urlencode 'query=成分 敏感肌 知性温柔' \
  --data 'limit=20'
```

带Campaign，只在SQL硬过滤合格池内召回：

```bash
curl --get 'http://127.0.0.1:8000/api/retrieval/keyword' \
  --data-urlencode 'query=成分 敏感肌' \
  --data 'campaign_id=cmp_0001' \
  --data 'limit=20'
```

结果包含：

- `keyword_score`：关键词覆盖与Trigram相似度的融合分数。
- `matched_terms`：实际命中的查询词。
- `matched_fields`：命中的类目、风格、主题或受众兴趣字段。
- `snippet`：命中位置附近的原始检索文本。
- `hard_filter_applied`：是否使用Campaign准入池。
- `warnings`：查询词与Campaign品类可能不一致时的非阻断提醒。

例如，食品饮料Campaign使用`成分 敏感肌`检索时，`成分`可同时用于食品和美妆，不会单独触发提醒；`敏感肌`指向美妆，因此响应会包含：

```json
{
  "code": "query_campaign_category_mismatch",
  "message": "查询词“敏感肌”主要关联“美妆个护”，可能与当前Campaign品类“食品饮料”不一致；请确认是否为跨品类需求。",
  "campaign_category": "食品饮料",
  "conflicting_terms": ["敏感肌"],
  "detected_categories": ["美妆个护"],
  "suggested_query": "食品饮料 探店 配料表 硬核测评"
}
```

该提醒不会自动删除结果，避免误伤真实的跨品类Campaign。用户确认后，可改用建议查询或继续当前检索。

当前关键词分数用于召回，不应直接作为最终达人适配度分数。后续会与向量召回通过RRF或归一化融合。

## Campaign基础查询与品类同义词扩展

带`campaign_id`时，关键词检索使用两组概念：

```text
Campaign基础概念 = 产品品类 + required_topics + tone_tags
用户焦点概念 = 用户输入query及其品类同义词
```

最终分数固定为：

```text
keyword_score = campaign_base_score × 40% + user_focus_score × 60%
```

同义词按原始概念成组计算，命中任一扩展词就视为该概念命中。例如食品Campaign中的`成分`扩展为：

```json
{
  "成分": ["成分", "配料表", "原料", "配方", "营养成分"]
}
```

原词精确命中的概念分为1.0，同义词精确命中略降权，以保留用户原始表达的轻微优先级。同义词数量不会稀释概念分数。

响应会分别返回：

- `campaign_base_score`
- `user_focus_score`
- `keyword_score`
- `query_expansions`
- `campaign_base_matched_terms`
- `matched_expanded_terms`

带Campaign的检索会为整次“硬过滤 + 关键词召回”创建同一条Recommendation Run，并返回`recommendation_run_id`和`evaluated_at`。两阶段共享同一个UTC判断时间。
