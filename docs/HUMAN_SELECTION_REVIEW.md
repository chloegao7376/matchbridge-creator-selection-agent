# 业务选号页与人工确认闭环

## 本地入口

先启动 FastAPI，再启动业务页面：

```bash
uvicorn app.main:app --reload
cd web
npm install
npm run dev
```

打开 <http://localhost:3000>。页面默认通过 `http://127.0.0.1:8000` 调用推荐服务；如地址不同，在 `web/.env.local` 中设置 `NEXT_PUBLIC_API_BASE_URL`。

## 页面流程

1. 选择 Campaign，输入本次关注点和候选人数。
2. 需要时展开高级设置，调整 Hybrid 召回参数或切换自定义 Fit 权重。
3. 生成推荐后，系统创建与 Recommendation Run 一一对应的人工审核草稿。
4. 业务人员可以锁定入选达人、排除达人并填写原因、恢复候选或人工加入达人。
5. REVIEW 达人必须先标记为人工复核通过，才可进入组合。
6. 人工加入或排除后，系统保留锁定与排除约束，重新运行预算组合优化。
7. 提交最终名单后，审核状态变为 `CONFIRMED`，后续修改返回 409，避免已确认结果被静默覆盖。

## API

```text
POST  /api/selection-reviews
GET   /api/selection-reviews/{review_id}
PATCH /api/selection-reviews/{review_id}/items/{account_id}
POST  /api/selection-reviews/{review_id}/recalculate
POST  /api/selection-reviews/{review_id}/confirm
```

`PATCH` 支持：

- `include`：人工加入并默认锁定；
- `exclude`：排除，且必须填写原因；
- `restore`：恢复为可选候选；
- `set_lock`：锁定或解除锁定当前入选达人；
- `resolve_risk`：将 REVIEW 处理为 `CLEARED` 或 `REJECTED`。

## 审计数据

- `selection_reviews`：一次推荐运行的人工审核状态、版本和最新组合摘要；
- `selection_review_items`：每位候选人的入选、排除、锁定、原因和风险复核状态；
- `selection_review_events`：创建、候选操作、组合重算和最终确认的事件记录。

受众重叠仍为代理估计。人工确认代表业务选号决策，不改变风险事件本身，也不构成法律或平台合规认定。
