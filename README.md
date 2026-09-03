# 达人智能匹配与选号模拟数据集

本项目生成一套完全虚构、可重复、可用于检索/排序/风控/离线评测的关系型数据。生成器仅依赖 Python 标准库。

## 生成数据

```bash
python3 generate_mock_data.py
```

默认使用固定随机种子 `20260831`，以 `2026-08-31` 为数据截止日，生成 320 位达人、约 400 个平台账号和 50 个 Campaign Brief。

自定义规模：

```bash
python3 generate_mock_data.py --creators 500 --briefs 80 --seed 42 --as-of 2026-08-31
```

注意：重新运行会重建整个 `data/` 目录。该目录只包含本生成器的派生数据。

## 文件说明

| 文件 | 粒度 | 主要用途 |
|---|---|---|
| `creators.jsonl` | 一位达人一行 | 虚构达人主体、类目与风格 |
| `accounts.jsonl` | 一个平台账号一行 | 平台、粉丝量级、类目、数据来源 |
| `audience_snapshots.jsonl` | 账号×日期 | 性别、年龄、地域、兴趣及可疑账号观测 |
| `account_metric_snapshots.jsonl` | 账号×周 | 粉丝曲线、互动率、播放量、评论重复率 |
| `content_items.jsonl` | 一条内容一行 | 文案、转写、广告标识、互动和评论情绪 |
| `rate_cards.jsonl` | 账号×内容形式 | 基础报价、套餐、权益和有效期 |
| `collaborations.jsonl` | 一次历史合作一行 | 品牌、时间、价格、履约和归因效果 |
| `risk_events.jsonl` | 一条风险线索一行 | 类型、证据、规则版本、置信度和审核状态 |
| `campaign_briefs.jsonl` | 一个Brief一行 | 人群、调性、平台、预算、竞品和权益约束 |
| `policy_rules.json` | 一条规则一项 | 风险线索规则及默认处置 |
| `manifest.json` | 数据集级 | 生成参数、行数、风险场景分布及免责声明 |

`data/evaluation/` 下的文件只能用于离线评测：

- `relevance_labels.jsonl`：Brief×账号的准入和相关性真值。
- `risk_scenario_ground_truth.jsonl`：风险注入真值。
- `history_availability_ground_truth.jsonl`：三档历史可用性规则的固定回归样本。
- `history_profile_ground_truth.jsonl`：账号级历史档位真值，默认约75%历史充分、20%历史有限、5%完全冷启动。
- `validation_report.json`：主外键、分布和指标一致性校验结果。

严禁把 `evaluation` 中的真值作为推荐服务输入，否则会造成标签泄漏。

## 推荐服务建议读取顺序

1. 读取 `campaign_briefs` 或接受用户输入，通过 LLM 转成同构 Brief。
2. 使用 `accounts`、`rate_cards` 和历史合作做硬条件过滤。
3. 使用达人类目/风格和近期内容做关键词 + Embedding 混合召回。
4. 从受众、效果、成本、履约计算分项适配度。
5. 独立读取 `risk_events`，输出 `PASS / REVIEW / BLOCK`，不要把严重风险简单折算成扣分。
6. 依据总预算做达人组合优化。
7. 用结构化证据生成推荐理由，并保存推荐运行快照。

## 合规边界

- 数据中所有姓名、品牌、URL、内容和指标均为虚构。
- `risk_events` 表示需要人工复核的风险线索，不构成违法、违规或事实认定。
- 项目接入真实平台数据时，应另外处理授权、最小化采集、数据来源、保存期限、访问权限和删除机制。
