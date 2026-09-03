export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://127.0.0.1:8000';

export const IS_DEMO_MODE =
  process.env.NEXT_PUBLIC_DEMO_MODE === 'true';

export type CampaignBrief = {
  campaign_id: string;
  brand_name: string;
  product_name: string;
  product_category: string;
  primary_kpi: string;
  target_platforms: string[];
  campaign_start_at: string;
  campaign_end_at: string;
  total_budget_cny: number;
  max_budget_per_creator_cny: number;
  creator_count: number;
};

export type EvidenceReason = {
  dimension: string;
  statement: string;
  evidence_values: Record<string, unknown>;
};

export type RecommendationCandidate = {
  account_id: string;
  creator_id: string;
  handle: string;
  platform: string;
  final_rank: number;
  fit_score: number;
  risk_decision: 'PASS' | 'REVIEW';
  selected_in_budget_plan: boolean;
  historical_data_availability: {
    tier: 'HISTORY_SUFFICIENT' | 'HISTORY_LIMITED' | 'COLD_START';
    tier_label: string;
    effective_history_n: number;
    history_reliability: number;
    valid_history_count: number;
    primary_kpi: string;
  };
  why_this_creator: EvidenceReason;
  why_in_final_combination: EvidenceReason | null;
  recommendation_reasons: EvidenceReason[];
  business_notes: string[];
};

export type BudgetCandidate = {
  account_id: string;
  estimated_cost_cny: number;
  primary_kpi: string;
  expected_primary_kpi: number;
  campaign_transfer_factor: number;
  confidence_factor: number;
  average_audience_similarity_to_selected: number;
  overlap_penalty_contribution: number;
};

export type BudgetSummary = {
  staffing_status: 'FULL' | 'PARTIAL' | 'EMPTY';
  primary_kpi: string;
  total_budget_cny: number;
  target_creator_count: number;
  selected_creator_count: number;
  selected_total_cost_cny: number;
  remaining_budget_cny: number;
  budget_utilization: number;
  selected_total_expected_primary_kpi: number;
  audience_overlap_penalty: number;
  overlap_adjusted_expected_primary_kpi: number;
  selected_average_fit_score: number;
  selected_candidates: BudgetCandidate[];
  warnings: string[];
};

export type RecommendationResponse = {
  campaign_id: string;
  query: string;
  recommendation_run_id: string;
  evaluated_at: string;
  warnings: { code: string; message: string }[];
  budget_optimization: BudgetSummary;
  candidates: RecommendationCandidate[];
};

export type ReviewItem = {
  account_id: string;
  handle: string;
  platform: string;
  final_rank: number;
  fit_score: number;
  risk_decision: 'PASS' | 'REVIEW';
  disposition: 'INCLUDED' | 'AVAILABLE' | 'EXCLUDED';
  source: 'SYSTEM' | 'OPTIMIZER' | 'HUMAN';
  locked: boolean;
  reason: string | null;
  risk_resolution: 'NOT_REQUIRED' | 'PENDING' | 'CLEARED' | 'REJECTED';
  updated_at: string;
};

export type SelectionReview = {
  review_id: string;
  run_id: string;
  campaign_id: string;
  status: 'DRAFT' | 'CONFIRMED';
  reviewer_name: string;
  version: number;
  optimization_summary: BudgetSummary;
  updated_at: string;
  confirmed_at: string | null;
  items: ReviewItem[];
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  headers.set('Content-Type', 'application/json');
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
  });
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null);
    const detail =
      payload && typeof payload === 'object' && 'detail' in payload
        ? String(payload.detail)
        : `请求失败（${response.status}）`;
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

const liveApi = {
  listBriefs: () => request<CampaignBrief[]>('/api/briefs?limit=50'),
  recommend: (payload: unknown) =>
    request<RecommendationResponse>('/api/recommendations/ranked', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  createReview: (runId: string, reviewerName: string) =>
    request<SelectionReview>('/api/selection-reviews', {
      method: 'POST',
      body: JSON.stringify({ run_id: runId, reviewer_name: reviewerName }),
    }),
  updateReviewItem: (
    reviewId: string,
    accountId: string,
    payload: Record<string, unknown>,
  ) =>
    request<SelectionReview>(
      `/api/selection-reviews/${reviewId}/items/${accountId}`,
      { method: 'PATCH', body: JSON.stringify(payload) },
    ),
  recalculate: (reviewId: string, actorName: string) =>
    request<SelectionReview>(`/api/selection-reviews/${reviewId}/recalculate`, {
      method: 'POST',
      body: JSON.stringify({ actor_name: actorName }),
    }),
  confirm: (reviewId: string, actorName: string) =>
    request<SelectionReview>(`/api/selection-reviews/${reviewId}/confirm`, {
      method: 'POST',
      body: JSON.stringify({ actor_name: actorName }),
    }),
};

const demoApiPromise = IS_DEMO_MODE
  ? import('./demo').then((module) => module.demoApi)
  : null;

export const api = IS_DEMO_MODE
  ? {
      listBriefs: async () => (await demoApiPromise!).listBriefs(),
      recommend: async (payload: unknown) =>
        (await demoApiPromise!).recommend(payload),
      createReview: async (runId: string, reviewerName: string) =>
        (await demoApiPromise!).createReview(runId, reviewerName),
      updateReviewItem: async (
        reviewId: string,
        accountId: string,
        payload: Record<string, unknown>,
      ) =>
        (await demoApiPromise!).updateReviewItem(reviewId, accountId, payload),
      recalculate: async (reviewId: string, _actorName: string) =>
        (await demoApiPromise!).recalculate(reviewId),
      confirm: async (reviewId: string, _actorName: string) =>
        (await demoApiPromise!).confirm(reviewId),
    }
  : liveApi;
