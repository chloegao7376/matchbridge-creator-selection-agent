# 第一阶段：FastAPI、PostgreSQL与JSONL导入

## 1. 创建隔离环境

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
cp .env.example .env
```

## 2. 启动PostgreSQL

如果`docker compose version`可用：

```bash
docker compose -p creator-agent up -d postgres
docker compose -p creator-agent ps
```

如果本机安装的是独立版`docker-compose`（本项目当前环境）：

```bash
docker-compose -p creator-agent up -d postgres
docker-compose -p creator-agent ps
```

首次下载`pgvector/pgvector:pg16`镜像可能需要几分钟。容器健康状态应显示为`healthy`。

## 3. 创建扩展和表

```bash
python -m app.db.init_db
```

该命令会创建`vector`扩展，并根据`app/models/entities.py`创建10张业务表。重复执行不会删除已有数据。

## 4. 导入JSONL

```bash
python scripts/import_jsonl.py --data-dir data
```

导入顺序遵循外键依赖，并使用主键Upsert；重复执行会更新现有行，不会重复插入。`data/evaluation/`不会被导入生产数据库。

## 5. 验证数据库行数

```bash
python scripts/verify_import.py --data-dir data
```

所有行都应以`OK`开头。

## 6. 启动FastAPI

```bash
uvicorn app.main:app --reload
```

打开：

- API文档：<http://127.0.0.1:8000/docs>
- 服务健康检查：<http://127.0.0.1:8000/health>
- 数据库健康检查：<http://127.0.0.1:8000/health/db>

## 7. 运行测试和静态检查

```bash
pytest
ruff check app scripts tests
```

Campaign Brief CRUD和硬条件过滤接口说明见[`docs/BRIEF_API.md`](docs/BRIEF_API.md)。

达人检索文档构建和关键词召回说明见[`docs/KEYWORD_RETRIEVAL.md`](docs/KEYWORD_RETRIEVAL.md)。

Embedding、pgvector 向量查询和 RRF 混合召回见[`docs/VECTOR_AND_HYBRID_RETRIEVAL.md`](docs/VECTOR_AND_HYBRID_RETRIEVAL.md)。

Hybrid Top-K 后的受众、效果、成本、质量和履约特征计算见[`docs/FEATURE_CALCULATION.md`](docs/FEATURE_CALCULATION.md)。

七维适配度权重、置信度收缩、缺失惩罚和最终排序见[`docs/FIT_RANKING.md`](docs/FIT_RANKING.md)。

业务基础参数、召回高级设置与Fit默认/自定义权重的分层配置见[`docs/RECOMMENDATION_CONFIGURATION.md`](docs/RECOMMENDATION_CONFIGURATION.md)。

总预算、目标人数、PASS资格、预期主KPI和受众重叠代理组合优化见[`docs/BUDGET_OPTIMIZATION.md`](docs/BUDGET_OPTIMIZATION.md)。更新代码后运行一次 `python -m app.db.init_db`，以创建 `recommendation_runs.budget_config` 审计字段。

推荐运行时间、BLOCK和竞品窗口的时间语义见[`docs/TIME_SEMANTICS.md`](docs/TIME_SEMANTICS.md)。

## 8. 启动业务选号页

保持 FastAPI 在 8000 端口运行，另开终端执行：

```bash
cd web
npm install
npm run dev
```

打开 <http://localhost:3000>。业务选号页、人工锁定/排除/加入、风险复核、组合重算和最终确认说明见[`docs/HUMAN_SELECTION_REVIEW.md`](docs/HUMAN_SELECTION_REVIEW.md)。首次更新到该版本后需再次运行 `python -m app.db.init_db` 创建人工审核与事件审计表。

## 常见问题

### 5432端口已占用

把`docker-compose.yml`中的端口改为例如`5433:5432`，同时把`.env`中的数据库地址改为：

```text
DATABASE_URL=postgresql+psycopg://creator_agent:creator_agent@localhost:5433/creator_agent
```

### API显示数据库不可用

依次检查：

```bash
docker-compose -p creator-agent ps
docker-compose -p creator-agent logs postgres
```

确认`.env`已从`.env.example`复制，且数据库端口一致。

### 重建数据库

普通开发中不要删除Volume。确实需要完全清空模拟数据库时，停止容器后显式执行：

```bash
docker-compose -p creator-agent down -v
```

这会永久删除容器中的数据库数据，随后需要重新执行初始化和导入步骤。
