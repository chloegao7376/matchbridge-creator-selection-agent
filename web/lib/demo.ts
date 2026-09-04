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
  platform: string;
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
  trafficQuality: number;
  costEfficiency: number;
  dataQuality: number;
  cost: number;
  expected: number;
  transfer: number;
  confidence: number;
  similarity: number;
  selected: boolean;
  topics: string[];
  audienceEvidence: string;
};

type DemoCampaignProfile = {
  brief: CampaignBrief;
  seeds: CandidateSeed[];
  kpiLabel: string;
};

const foodSeeds: CandidateSeed[] = [
  {
    accountId: 'acc_demo_001',
    creatorId: 'cr_demo_001',
    handle: '食研所阿宁_小红书',
    platform: '小红书',
    rank: 1,
    fit: 86.4,
    risk: 'PASS',
    tier: 'HISTORY_SUFFICIENT',
    tierLabel: '历史充分',
    effectiveN: 6.8,
    reliability: 0.96,
    content: 0.91,
    audience: 0.84,
    engagement: 0.068,
    roi: 1.72,
    delivery: 1,
    trafficQuality: 0.88,
    costEfficiency: 0.82,
    dataQuality: 0.92,
    cost: 26800,
    expected: 438,
    transfer: 0.86,
    confidence: 0.94,
    similarity: 0.31,
    selected: true,
    topics: ['配料表', '高蛋白早餐', '轻食'],
    audienceEvidence: '健康饮食与早餐消费人群',
  },
  {
    accountId: 'acc_demo_002',
    creatorId: 'cr_demo_002',
    handle: '配料表研究员Mia_小红书',
    platform: '小红书',
    rank: 2,
    fit: 83.7,
    risk: 'PASS',
    tier: 'HISTORY_LIMITED',
    tierLabel: '历史有限',
    effectiveN: 1.4,
    reliability: 0.47,
    content: 0.95,
    audience: 0.79,
    engagement: 0.074,
    roi: 1.31,
    delivery: 1,
    trafficQuality: 0.84,
    costEfficiency: 0.89,
    dataQuality: 0.71,
    cost: 18500,
    expected: 326,
    transfer: 0.88,
    confidence: 0.78,
    similarity: 0.38,
    selected: true,
    topics: ['配料表', '食品成分', '营养测评'],
    audienceEvidence: '成分关注与理性消费人群',
  },
  {
    accountId: 'acc_demo_003',
    creatorId: 'cr_demo_003',
    handle: '轻食日记Lynn_小红书',
    platform: '小红书',
    rank: 3,
    fit: 80.9,
    risk: 'PASS',
    tier: 'HISTORY_SUFFICIENT',
    tierLabel: '历史充分',
    effectiveN: 5.3,
    reliability: 0.91,
    content: 0.82,
    audience: 0.88,
    engagement: 0.061,
    roi: 1.58,
    delivery: 0.96,
    trafficQuality: 0.86,
    costEfficiency: 0.84,
    dataQuality: 0.9,
    cost: 23200,
    expected: 371,
    transfer: 0.82,
    confidence: 0.91,
    similarity: 0.34,
    selected: true,
    topics: ['轻食', '早餐搭配', '控卡饮食'],
    audienceEvidence: '都市轻食与体重管理人群',
  },
  {
    accountId: 'acc_demo_004',
    creatorId: 'cr_demo_004',
    handle: '城市早餐计划_小红书',
    platform: '小红书',
    rank: 4,
    fit: 78.1,
    risk: 'REVIEW',
    tier: 'HISTORY_SUFFICIENT',
    tierLabel: '历史充分',
    effectiveN: 4.7,
    reliability: 0.88,
    content: 0.79,
    audience: 0.81,
    engagement: 0.083,
    roi: 1.44,
    delivery: 0.93,
    trafficQuality: 0.81,
    costEfficiency: 0.85,
    dataQuality: 0.87,
    cost: 21500,
    expected: 352,
    transfer: 0.78,
    confidence: 0.89,
    similarity: 0.43,
    selected: false,
    topics: ['早餐', '通勤饮食', '便利食品'],
    audienceEvidence: '一二线城市通勤早餐人群',
  },
  {
    accountId: 'acc_demo_005',
    creatorId: 'cr_demo_005',
    handle: '新味觉Yuki_小红书',
    platform: '小红书',
    rank: 5,
    fit: 75.6,
    risk: 'REVIEW',
    tier: 'COLD_START',
    tierLabel: '完全冷启动',
    effectiveN: 0,
    reliability: 0.2,
    content: 0.89,
    audience: 0.76,
    engagement: 0.059,
    roi: 0,
    delivery: 0.8,
    trafficQuality: 0.78,
    costEfficiency: 0.94,
    dataQuality: 0.52,
    cost: 9800,
    expected: 184,
    transfer: 0.76,
    confidence: 0.55,
    similarity: 0.29,
    selected: false,
    topics: ['新品试吃', '配料解读', '早餐'],
    audienceEvidence: '新品尝鲜与食品测评人群',
  },
];

const beautySeeds: CandidateSeed[] = [
  {
    accountId: 'acc_demo_101',
    creatorId: 'cr_demo_101',
    handle: '敏感肌研究所Rita_小红书',
    platform: '小红书',
    rank: 1,
    fit: 89.2,
    risk: 'PASS',
    tier: 'HISTORY_SUFFICIENT',
    tierLabel: '历史充分',
    effectiveN: 7.2,
    reliability: 0.97,
    content: 0.96,
    audience: 0.9,
    engagement: 0.081,
    roi: 1.86,
    delivery: 1,
    trafficQuality: 0.91,
    costEfficiency: 0.78,
    dataQuality: 0.94,
    cost: 42000,
    expected: 16800,
    transfer: 0.91,
    confidence: 0.95,
    similarity: 0.29,
    selected: true,
    topics: ['敏感肌', '屏障修护', '舒缓精华'],
    audienceEvidence: '敏感肌与功效护肤核心人群',
  },
  {
    accountId: 'acc_demo_102',
    creatorId: 'cr_demo_102',
    handle: '成分党小沐_抖音',
    platform: '抖音',
    rank: 2,
    fit: 85.8,
    risk: 'PASS',
    tier: 'HISTORY_LIMITED',
    tierLabel: '历史有限',
    effectiveN: 1.8,
    reliability: 0.52,
    content: 0.93,
    audience: 0.84,
    engagement: 0.092,
    roi: 1.47,
    delivery: 0.96,
    trafficQuality: 0.87,
    costEfficiency: 0.75,
    dataQuality: 0.73,
    cost: 48000,
    expected: 21300,
    transfer: 0.87,
    confidence: 0.8,
    similarity: 0.35,
    selected: true,
    topics: ['护肤成分', '敏感肌', '精华测评'],
    audienceEvidence: '关注成分与功效验证的年轻人群',
  },
  {
    accountId: 'acc_demo_103',
    creatorId: 'cr_demo_103',
    handle: '护肤实验室Anya_小红书',
    platform: '小红书',
    rank: 3,
    fit: 82.6,
    risk: 'PASS',
    tier: 'HISTORY_SUFFICIENT',
    tierLabel: '历史充分',
    effectiveN: 5.9,
    reliability: 0.93,
    content: 0.87,
    audience: 0.86,
    engagement: 0.076,
    roi: 1.69,
    delivery: 0.98,
    trafficQuality: 0.89,
    costEfficiency: 0.83,
    dataQuality: 0.91,
    cost: 35600,
    expected: 14200,
    transfer: 0.84,
    confidence: 0.92,
    similarity: 0.32,
    selected: true,
    topics: ['屏障修护', '功效实测', '换季护肤'],
    audienceEvidence: '换季修护与科学护肤人群',
  },
  {
    accountId: 'acc_demo_104',
    creatorId: 'cr_demo_104',
    handle: '屏障修护笔记_小红书',
    platform: '小红书',
    rank: 4,
    fit: 79.4,
    risk: 'REVIEW',
    tier: 'HISTORY_SUFFICIENT',
    tierLabel: '历史充分',
    effectiveN: 4.4,
    reliability: 0.86,
    content: 0.9,
    audience: 0.8,
    engagement: 0.084,
    roi: 1.38,
    delivery: 0.91,
    trafficQuality: 0.8,
    costEfficiency: 0.86,
    dataQuality: 0.85,
    cost: 29800,
    expected: 12100,
    transfer: 0.8,
    confidence: 0.87,
    similarity: 0.41,
    selected: false,
    topics: ['皮肤屏障', '泛红舒缓', '敏感肌'],
    audienceEvidence: '泛红、干敏与屏障受损人群',
  },
  {
    accountId: 'acc_demo_105',
    creatorId: 'cr_demo_105',
    handle: '新肌观察员Nono_抖音',
    platform: '抖音',
    rank: 5,
    fit: 74.8,
    risk: 'REVIEW',
    tier: 'COLD_START',
    tierLabel: '完全冷启动',
    effectiveN: 0,
    reliability: 0.2,
    content: 0.86,
    audience: 0.74,
    engagement: 0.071,
    roi: 0,
    delivery: 0.8,
    trafficQuality: 0.76,
    costEfficiency: 0.92,
    dataQuality: 0.5,
    cost: 13800,
    expected: 6400,
    transfer: 0.73,
    confidence: 0.53,
    similarity: 0.27,
    selected: false,
    topics: ['新品护肤', '使用体验', '平价精华'],
    audienceEvidence: '护肤新品尝鲜与学生人群',
  },
];

const campaignProfiles = new Map<string, DemoCampaignProfile>([
  ['cmp_0001', { brief: demoBriefs[0], seeds: foodSeeds, kpiLabel: '转化' }],
  ['cmp_0002', { brief: demoBriefs[1], seeds: beautySeeds, kpiLabel: '互动' }],
]);

function profileFor(campaignId?: string): DemoCampaignProfile {
  return (
    campaignProfiles.get(campaignId ?? '') ?? campaignProfiles.get('cmp_0001')!
  );
}

function evidence(
  seed: CandidateSeed,
): RecommendationCandidate['recommendation_reasons'] {
  return [
    {
      dimension: 'content_relevance',
      statement: `内容相关性${(seed.content * 100).toFixed(1)}分；近期内容命中：${seed.topics.join('、')}。`,
      evidence_values: {
        content_relevance_score: seed.content,
        matched_terms: seed.topics,
      },
    },
    {
      dimension: 'audience_fit',
      statement: `受众适配度${(seed.audience * 100).toFixed(1)}分；主要覆盖${seed.audienceEvidence}。`,
      evidence_values: {
        audience_fit_score: seed.audience,
        target_age_share: Math.min(seed.audience * 0.76, 0.72),
      },
    },
    {
      dimension: 'performance',
      statement: `近30日互动率${(seed.engagement * 100).toFixed(1)}%，历史平均ROI ${seed.roi.toFixed(2)}。`,
      evidence_values: {
        performance_score: Math.min(seed.roi / 2, 1),
        engagement_rate_30d: seed.engagement,
        historical_average_roi: seed.roi,
      },
    },
    {
      dimension: 'traffic_quality',
      statement: '流量结构稳定，异常互动和重复评论比例处于可接受范围。',
      evidence_values: { traffic_quality_score: seed.trafficQuality },
    },
    {
      dimension: 'delivery_reliability',
      statement: `历史准时交付率${(seed.delivery * 100).toFixed(0)}%。`,
      evidence_values: {
        delivery_reliability_score: seed.delivery,
        historical_on_time_delivery_rate: seed.delivery,
      },
    },
    {
      dimension: 'cost_efficiency',
      statement: `估算报价¥${seed.cost.toLocaleString('zh-CN')}，未超过单人预算。`,
      evidence_values: {
        cost_efficiency_score: seed.costEfficiency,
        estimated_cost_cny: seed.cost,
      },
    },
    {
      dimension: 'data_quality',
      statement: '账号、受众与内容数据更新时间符合本次评估要求。',
      evidence_values: { data_quality_score: seed.dataQuality },
    },
  ];
}

function makeCandidates(
  profile: DemoCampaignProfile,
): RecommendationCandidate[] {
  return profile.seeds.map((seed) => ({
    account_id: seed.accountId,
    creator_id: seed.creatorId,
    handle: seed.handle,
    platform: seed.platform,
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
      primary_kpi: profile.brief.primary_kpi,
    },
    why_this_creator: {
      dimension: 'candidate_selection',
      statement: `该达人以业务适配度${seed.fit.toFixed(1)}分进入推荐候选，${seed.risk === 'PASS' ? '当前风险审核通过' : '存在待人工复核风险线索'}；主要优势来自内容相关性、受众适配度与流量质量。`,
      evidence_values: {
        fit_score: seed.fit,
        final_rank: seed.rank,
        risk_decision: seed.risk,
      },
    },
    why_in_final_combination: seed.selected
      ? {
          dimension: 'portfolio_selection',
          statement: `该达人进入最终组合：预计贡献${profile.kpiLabel}${seed.expected.toFixed(0)}，Campaign迁移系数${(seed.transfer * 100).toFixed(1)}%，置信修正系数${(seed.confidence * 100).toFixed(1)}%；在预算约束下可提升组合预期收益。`,
          evidence_values: {
            expected_primary_kpi: seed.expected,
            campaign_transfer_factor: seed.transfer,
            confidence_factor: seed.confidence,
          },
        }
      : null,
    recommendation_reasons: evidence(seed),
    business_notes: [
      '内容契合度为系统初筛结果，最终合作前需人工确认。',
      ...(seed.tier === 'HISTORY_LIMITED'
        ? [
            '历史数据有限，已降低历史效果权重并提高稳定性信号权重，建议人工复核。',
          ]
        : seed.tier === 'COLD_START'
          ? ['该达人为完全冷启动，不自动进入预算组合，建议人工复核。']
          : []),
      ...(seed.risk === 'REVIEW'
        ? ['该达人存在待复核风险线索，合作前需完成人工审核。']
        : []),
    ],
  }));
}

function makeBudget(
  selectedIds: string[],
  profile: DemoCampaignProfile,
): BudgetSummary {
  const seedByAccount = new Map(
    profile.seeds.map((seed) => [seed.accountId, seed]),
  );
  const selected = selectedIds
    .map((id) => seedByAccount.get(id)!)
    .filter(Boolean);
  const selectedCandidates: BudgetCandidate[] = selected.map((seed) => ({
    account_id: seed.accountId,
    estimated_cost_cny: seed.cost,
    primary_kpi: profile.brief.primary_kpi,
    expected_primary_kpi: seed.expected,
    campaign_transfer_factor: seed.transfer,
    confidence_factor: seed.confidence,
    average_audience_similarity_to_selected: seed.similarity,
    overlap_penalty_contribution: seed.expected * seed.similarity * 0.08,
  }));
  const totalCost = selected.reduce((sum, seed) => sum + seed.cost, 0);
  const expected = selected.reduce((sum, seed) => sum + seed.expected, 0);
  const overlapPenalty = selectedCandidates.reduce(
    (sum, item) => sum + item.overlap_penalty_contribution,
    0,
  );
  return {
    staffing_status:
      selected.length === profile.brief.creator_count
        ? 'FULL'
        : selected.length
          ? 'PARTIAL'
          : 'EMPTY',
    primary_kpi: profile.brief.primary_kpi,
    total_budget_cny: profile.brief.total_budget_cny,
    target_creator_count: profile.brief.creator_count,
    selected_creator_count: selected.length,
    selected_total_cost_cny: totalCost,
    remaining_budget_cny: profile.brief.total_budget_cny - totalCost,
    budget_utilization: totalCost / profile.brief.total_budget_cny,
    selected_total_expected_primary_kpi: expected,
    audience_overlap_penalty: overlapPenalty,
    overlap_adjusted_expected_primary_kpi: expected - overlapPenalty,
    selected_average_fit_score: selected.length
      ? selected.reduce((sum, seed) => sum + seed.fit, 0) / selected.length
      : 0,
    selected_candidates: selectedCandidates,
    warnings: ['2位REVIEW候选未被自动纳入预算组合，需人工复核后再决定。'],
  };
}

function makeRecommendation(
  query = '配料表',
  campaignId = 'cmp_0001',
): RecommendationResponse {
  const profile = profileFor(campaignId);
  return {
    campaign_id: profile.brief.campaign_id,
    query,
    recommendation_run_id: `run_${profile.brief.campaign_id}_demo`,
    evaluated_at: new Date().toISOString(),
    warnings: [],
    budget_optimization: makeBudget(
      profile.seeds
        .filter((seed) => seed.selected)
        .map((seed) => seed.accountId),
      profile,
    ),
    candidates: makeCandidates(profile),
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
  const profile = profileFor(currentReview.campaign_id);
  const locked = currentReview.items.filter(
    (item) => item.disposition === 'INCLUDED' && item.locked,
  );
  const available = currentReview.items
    .filter((item) => item.disposition !== 'EXCLUDED' && !locked.includes(item))
    .filter(
      (item) =>
        item.risk_decision === 'PASS' || item.risk_resolution === 'CLEARED',
    )
    .sort((a, b) => a.final_rank - b.final_rank);
  const selected = [...locked, ...available].slice(
    0,
    profile.brief.creator_count,
  );
  const selectedIds = new Set(selected.map((item) => item.account_id));
  currentReview.items = currentReview.items.map((item) =>
    item.disposition === 'EXCLUDED'
      ? item
      : {
          ...item,
          disposition: selectedIds.has(item.account_id)
            ? 'INCLUDED'
            : 'AVAILABLE',
        },
  );
  currentReview.optimization_summary = makeBudget([...selectedIds], profile);
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
      review_id: `review_${currentRecommendation.campaign_id}_demo`,
      run_id: currentRecommendation.recommendation_run_id,
      campaign_id: currentRecommendation.campaign_id,
      status: 'DRAFT',
      reviewer_name: reviewerName,
      version: 1,
      optimization_summary: structuredClone(
        currentRecommendation.budget_optimization,
      ),
      updated_at: now,
      confirmed_at: null,
      items: currentRecommendation.candidates.map<ReviewItem>((candidate) => ({
        account_id: candidate.account_id,
        handle: candidate.handle,
        platform: candidate.platform,
        final_rank: candidate.final_rank,
        fit_score: candidate.fit_score,
        risk_decision: candidate.risk_decision,
        disposition: candidate.selected_in_budget_plan
          ? 'INCLUDED'
          : 'AVAILABLE',
        source: candidate.selected_in_budget_plan ? 'OPTIMIZER' : 'SYSTEM',
        locked: false,
        reason: null,
        risk_resolution:
          candidate.risk_decision === 'PASS' ? 'NOT_REQUIRED' : 'PENDING',
        updated_at: now,
      })),
    };
    return cloneReview();
  },
  async updateReviewItem(
    _reviewId: string,
    accountId: string,
    payload: Record<string, unknown>,
  ) {
    await wait(100);
    if (!currentReview) throw new Error('演示审核尚未初始化');
    const action = textValue(payload.action, '');
    const now = new Date().toISOString();
    currentReview.items = currentReview.items.map((item) => {
      if (item.account_id !== accountId) return item;
      if (action === 'exclude')
        return {
          ...item,
          disposition: 'EXCLUDED',
          source: 'HUMAN',
          locked: false,
          reason: textValue(payload.reason, '人工排除'),
          updated_at: now,
        };
      if (action === 'restore')
        return {
          ...item,
          disposition: 'AVAILABLE',
          source: 'HUMAN',
          reason: null,
          updated_at: now,
        };
      if (action === 'include')
        return {
          ...item,
          disposition: 'INCLUDED',
          source: 'HUMAN',
          locked: Boolean(payload.locked),
          updated_at: now,
        };
      if (action === 'set_lock')
        return {
          ...item,
          locked: Boolean(payload.locked),
          source: 'HUMAN',
          updated_at: now,
        };
      if (action === 'resolve_risk')
        return {
          ...item,
          risk_resolution: 'CLEARED',
          reason: textValue(payload.reason, '人工复核通过'),
          source: 'HUMAN',
          updated_at: now,
        };
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
