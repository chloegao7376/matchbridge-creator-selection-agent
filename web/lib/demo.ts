import type {
  BudgetCandidate,
  BudgetSummary,
  CampaignBrief,
  RecommendationCandidate,
  RecommendationResponse,
  ReviewItem,
  SelectionReview,
} from './api';

const wait = (milliseconds = 180) =>
  new Promise((resolve) => setTimeout(resolve, milliseconds));

const textValue = (value: unknown, fallback: string) =>
  typeof value === 'string' ? value : fallback;

export const demoBriefs: CampaignBrief[] = [
  {
    campaign_id: 'cmp_0001',
    brand_name: '一日食光',
    product_name: '高蛋白燕麦杯',
    product_category: '食品饮料',
    primary_kpi: 'conversions',
    target_platforms: ['小红书'],
    campaign_start_at: '2026-09-15T00:00:00Z',
    campaign_end_at: '2026-10-15T00:00:00Z',
    total_budget_cny: 120000,
    max_budget_per_creator_cny: 40000,
    creator_count: 3,
  },
  {
    campaign_id: 'cmp_0002',
    brand_name: '澄光护肤',
    product_name: '舒缓修护精华',
    product_category: '美妆个护',
    primary_kpi: 'engagements',
    target_platforms: ['小红书', '抖音'],
    campaign_start_at: '2026-10-01T00:00:00Z',
    campaign_end_at: '2026-10-31T00:00:00Z',
    total_budget_cny: 180000,
    max_budget_per_creator_cny: 50000,
    creator_count: 3,
  },
];

type CandidateSeed = {
  accountId: string;
  creatorId: string;
  handle: string;
  rank: number;
  fit: number;
  risk: 'PASS' | 'REVIEW';
  tier: 'HISTORY_SUFFICIENT' | 'HISTORY_LIMITED' | 'COLD_START';
  tierLabel: string;
  effectiveN: number;
  reliability: number;
  content: number;
  audience: number;
  engagement: number;
  roi: number;
  delivery: number;
  cost: number;
  expected: number;
  transfer: number;
  confidence: number;
  similarity: number;
  selected: boolean;
};

const seeds: CandidateSeed[] = [
  {
    accountId: 'acc_demo_001', creatorId: 'cr_demo_001', handle: '食研所阿宁_小红书', rank: 1,
    fit: 86.4, risk: 'PASS', tier: 'HISTORY_SUFFICIENT', tierLabel: '历史充分', effectiveN: 6.8,
    reliability: 0.96, content: 0.91, audience: 0.84, engagement: 0.068, roi: 1.72,
    delivery: 1, cost: 26800, expected: 438, transfer: 0.86, confidence: 0.94, similarity: 0.31, selected: true,
  },
  {
    accountId: 'acc_demo_002', creatorId: 'cr_demo_002', handle: '配料表研究员Mia_小红书', rank: 2,
    fit: 83.7, risk: 'PASS', tier: 'HISTORY_LIMITED', tierLabel: '历史有限', effectiveN: 1.4,
    reliability: 0.47, content: 0.95, audience: 0.79, engagement: 0.074, roi: 1.31,
    delivery: 1, cost: 18500, expected: 326, transfer: 0.88, confidence: 0.78, similarity: 0.38, selected: true,
  },
  {
    accountId: 'acc_demo_003', creatorId: 'cr_demo_003', handle: '轻食日记Lynn_小红书', rank: 3,
    fit: 80.9, risk: 'PASS', tier: 'HISTORY_SUFFICIENT', tierLabel: '历史充分', effectiveN: 5.3,
    reliability: 0.91, content: 0.82, audience: 0.88, engagement: 0.061, roi: 1.58,
    delivery: 0.96, cost: 23200, expected: 371, transfer: 0.82, confidence: 0.91, similarity: 0.34, selected: true,
  },
  {
    accountId: 'acc_demo_004', creatorId: 'cr_demo_004', handle: '城市早餐计划_小红书', rank: 4,
    fit: 78.1, risk: 'REVIEW', tier: 'HISTORY_SUFFICIENT', tierLabel: '历史充分', effectiveN: 4.7,
    reliability: 0.88, content: 0.79, audience: 0.81, engagement: 0.083, roi: 1.44,
    delivery: 0.93, cost: 21500, expected: 352, transfer: 0.78, confidence: 0.89, similarity: 0.43, selected: false,
  },
  {
    accountId: 'acc_demo_005', creatorId: 'cr_demo_005', handle: '新味觉Yuki_小红书', rank: 5,
    fit: 75.6, risk: 'REVIEW', tier: 'COLD_START', tierLabel: '完全冷启动', effectiveN: 0,
    reliability: 0.2, content: 0.89, audience: 0.76, engagement: 0.059, roi: 0,
    delivery: 0.8, cost: 9800, expected: 184, transfer: 0.76, confidence: 0.55, similarity: 0.29, selected: false,
  },
];

function evidence(seed: CandidateSeed): RecommendationCandidate['recommendation_reasons'] {
  return [
    {
      dimension: 'content_relevance',
      statement: `内容相关性${(seed.content * 100).toFixed(1)}分；近期内容命中：配料表、高蛋白早餐、轻食。`,
      evidence_values: { content_relevance_score: seed.content, matched_terms: ['配料表', '高蛋白早餐', '轻食'] },
    },
    {
      dimension: 'audience_fit',
      statement: `受众适配度${(seed.audience * 100).toFixed(1)}分；核心受众与Campaign目标人群高度重合。`,
      evidence_values: { audience_fit_score: seed.audience, target_age_share: 0.64 },
    },
    {
      dimension: 'performance',
      statement: `近30日互动率${(seed.engagement * 100).toFixed(1)}%，历史平均ROI ${seed.roi.toFixed(2)}。`,
      evidence_values: { performance_score: Math.min(seed.roi / 2, 1), engagement_rate_30d: seed.engagement, historical_average_roi: seed.roi },
    },
    {
      dimension: 'traffic_quality',
      statement: '流量结构稳定，异常互动和重复评论比例处于可接受范围。',
      evidence_values: { traffic_quality_score: 0.86 },
    },
    {
      dimension: 'delivery_reliability',
      statement: `历史准时交付率${(seed.delivery * 100).toFixed(0)}%。`,
      evidence_values: { delivery_reliability_score: seed.delivery, historical_on_time_delivery_rate: seed.delivery },
    },
    {
      dimension: 'cost_efficiency',
      statement: `估算报价¥${seed.cost.toLocaleString('zh-CN')}，未超过单人预算。`,
      evidence_values: { cost_efficiency_score: 0.82, estimated_cost_cny: seed.cost },
    },
    {
      dimension: 'data_quality',
      statement: '账号、受众与内容数据更新时间符合本次评估要求。',
      evidence_values: { data_quality_score: seed.tier === 'COLD_START' ? 0.52 : 0.9 },
    },
  ];
}

export const demoCandidates: RecommendationCandidate[] = seeds.map((seed) => ({
  account_id: seed.accountId,
  creator_id: seed.creatorId,
  handle: seed.handle,
  platform: '小红书',
  final_rank: seed.rank,
  fit_score: seed.fit,
  risk_decision: seed.risk,
  selected_in_budget_plan: seed.selected,
  historical_data_availability: {
    tier: seed.tier,
    tier_label: seed.tierLabel,
    effective_history_n: seed.effectiveN,
    history_reliability: seed.reliability,
    valid_history_count: Math.round(seed.effectiveN),
    primary_kpi: 'conversions',
  },
  why_this_creator: {
    dimension: 'candidate_selection',
    statement: `该达人以业务适配度${seed.fit.toFixed(1)}分进入推荐候选，${seed.risk === 'PASS' ? '当前风险审核通过' : '存在待人工复核风险线索'}；主要优势来自内容相关性、受众适配度与流量质量。`,
    evidence_values: { fit_score: seed.fit, final_rank: seed.rank, risk_decision: seed.risk },
  },
  why_in_final_combination: seed.selected
    ? {
        dimension: 'portfolio_selection',
        statement: `该达人进入最终组合：预计贡献转化${seed.expected.toFixed(0)}，Campaign迁移系数${(seed.transfer * 100).toFixed(1)}%，置信修正系数${(seed.confidence * 100).toFixed(1)}%；在预算约束下可提升组合预期收益。`,
        evidence_values: { expected_primary_kpi: seed.expected, campaign_transfer_factor: seed.transfer, confidence_factor: seed.confidence },
      }
    : null,
  recommendation_reasons: evidence(seed),
  business_notes: [
    '内容契合度为系统初筛结果，最终合作前需人工确认。',
    ...(seed.tier === 'HISTORY_LIMITED'
      ? ['历史数据有限，已降低历史效果权重并提高稳定性信号权重，建议人工复核。']
      : seed.tier === 'COLD_START'
        ? ['该达人为完全冷启动，不自动进入预算组合，建议人工复核。']
        : []),
    ...(seed.risk === 'REVIEW' ? ['该达人存在待复核风险线索，合作前需完成人工审核。'] : []),
  ],
}));

const seedByAccount = new Map(seeds.map((seed) => [seed.accountId, seed]));

function makeBudget(selectedIds: string[]): BudgetSummary {
  const selected = selectedIds.map((id) => seedByAccount.get(id)!).filter(Boolean);
  const selectedCandidates: BudgetCandidate[] = selected.map((seed) => ({
    account_id: seed.accountId,
    estimated_cost_cny: seed.cost,
    primary_kpi: 'conversions',
    expected_primary_kpi: seed.expected,
    campaign_transfer_factor: seed.transfer,
    confidence_factor: seed.confidence,
    average_audience_similarity_to_selected: seed.similarity,
    overlap_penalty_contribution: seed.expected * seed.similarity * 0.08,
  }));
  const totalCost = selected.reduce((sum, seed) => sum + seed.cost, 0);
  const expected = selected.reduce((sum, seed) => sum + seed.expected, 0);
  const overlapPenalty = selectedCandidates.reduce((sum, item) => sum + item.overlap_penalty_contribution, 0);
  return {
    staffing_status: selected.length === 3 ? 'FULL' : selected.length ? 'PARTIAL' : 'EMPTY',
    primary_kpi: 'conversions',
    total_budget_cny: 120000,
    target_creator_count: 3,
    selected_creator_count: selected.length,
    selected_total_cost_cny: totalCost,
    remaining_budget_cny: 120000 - totalCost,
    budget_utilization: totalCost / 120000,
    selected_total_expected_primary_kpi: expected,
    audience_overlap_penalty: overlapPenalty,
    overlap_adjusted_expected_primary_kpi: expected - overlapPenalty,
    selected_average_fit_score: selected.length ? selected.reduce((sum, seed) => sum + seed.fit, 0) / selected.length : 0,
    selected_candidates: selectedCandidates,
    warnings: ['2位REVIEW候选未被自动纳入预算组合，需人工复核后再决定。'],
  };
}

function makeRecommendation(query = '配料表', campaignId = 'cmp_0001'): RecommendationResponse {
  return {
    campaign_id: campaignId,
    query,
    recommendation_run_id: 'run_portfolio_demo',
    evaluated_at: new Date().toISOString(),
    warnings: [],
    budget_optimization: makeBudget(seeds.filter((seed) => seed.selected).map((seed) => seed.accountId)),
    candidates: structuredClone(demoCandidates),
  };
}

let currentRecommendation = makeRecommendation();
let currentReview: SelectionReview | null = null;

function cloneReview() {
  if (!currentReview) throw new Error('演示审核尚未初始化');
  return structuredClone(currentReview);
}

function rebuildBudget() {
  if (!currentReview) return;
  const locked = currentReview.items.filter((item) => item.disposition === 'INCLUDED' && item.locked);
  const available = currentReview.items
    .filter((item) => item.disposition !== 'EXCLUDED' && !locked.includes(item))
    .filter((item) => item.risk_decision === 'PASS' || item.risk_resolution === 'CLEARED')
    .sort((a, b) => a.final_rank - b.final_rank);
  const selected = [...locked, ...available].slice(0, 3);
  const selectedIds = new Set(selected.map((item) => item.account_id));
  currentReview.items = currentReview.items.map((item) =>
    item.disposition === 'EXCLUDED'
      ? item
      : { ...item, disposition: selectedIds.has(item.account_id) ? 'INCLUDED' : 'AVAILABLE' },
  );
  currentReview.optimization_summary = makeBudget([...selectedIds]);
  currentReview.version += 1;
  currentReview.updated_at = new Date().toISOString();
}

export const demoApi = {
  async listBriefs() {
    await wait(120);
    return structuredClone(demoBriefs);
  },
  async recommend(payload: unknown) {
    await wait();
    const input = payload as { campaign_id?: string; query?: string };
    currentRecommendation = makeRecommendation(input.query, input.campaign_id);
    currentReview = null;
    return structuredClone(currentRecommendation);
  },
  async createReview(_runId: string, reviewerName: string) {
    await wait(120);
    const now = new Date().toISOString();
    currentReview = {
      review_id: 'review_portfolio_demo',
      run_id: currentRecommendation.recommendation_run_id,
      campaign_id: currentRecommendation.campaign_id,
      status: 'DRAFT',
      reviewer_name: reviewerName,
      version: 1,
      optimization_summary: structuredClone(currentRecommendation.budget_optimization),
      updated_at: now,
      confirmed_at: null,
      items: currentRecommendation.candidates.map<ReviewItem>((candidate) => ({
        account_id: candidate.account_id,
        handle: candidate.handle,
        platform: candidate.platform,
        final_rank: candidate.final_rank,
        fit_score: candidate.fit_score,
        risk_decision: candidate.risk_decision,
        disposition: candidate.selected_in_budget_plan ? 'INCLUDED' : 'AVAILABLE',
        source: candidate.selected_in_budget_plan ? 'OPTIMIZER' : 'SYSTEM',
        locked: false,
        reason: null,
        risk_resolution: candidate.risk_decision === 'PASS' ? 'NOT_REQUIRED' : 'PENDING',
        updated_at: now,
      })),
    };
    return cloneReview();
  },
  async updateReviewItem(_reviewId: string, accountId: string, payload: Record<string, unknown>) {
    await wait(100);
    if (!currentReview) throw new Error('演示审核尚未初始化');
    const action = textValue(payload.action, '');
    const now = new Date().toISOString();
    currentReview.items = currentReview.items.map((item) => {
      if (item.account_id !== accountId) return item;
      if (action === 'exclude') return { ...item, disposition: 'EXCLUDED', source: 'HUMAN', locked: false, reason: textValue(payload.reason, '人工排除'), updated_at: now };
      if (action === 'restore') return { ...item, disposition: 'AVAILABLE', source: 'HUMAN', reason: null, updated_at: now };
      if (action === 'include') return { ...item, disposition: 'INCLUDED', source: 'HUMAN', locked: Boolean(payload.locked), updated_at: now };
      if (action === 'set_lock') return { ...item, locked: Boolean(payload.locked), source: 'HUMAN', updated_at: now };
      if (action === 'resolve_risk') return { ...item, risk_resolution: 'CLEARED', reason: textValue(payload.reason, '人工复核通过'), source: 'HUMAN', updated_at: now };
      return item;
    });
    currentReview.updated_at = now;
    return cloneReview();
  },
  async recalculate(_reviewId?: string) {
    await wait();
    rebuildBudget();
    return cloneReview();
  },
  async confirm(_reviewId?: string) {
    await wait();
    if (!currentReview) throw new Error('演示审核尚未初始化');
    currentReview.status = 'CONFIRMED';
    currentReview.confirmed_at = new Date().toISOString();
    currentReview.updated_at = currentReview.confirmed_at;
    return cloneReview();
  },
};
