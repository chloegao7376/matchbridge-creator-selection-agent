'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronDown,
  CircleDollarSign,
  FileClock,
  LayoutGrid,
  Loader2,
  Lock,
  LockOpen,
  RefreshCw,
  Search,
  ShieldAlert,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Undo2,
  UserPlus,
  Users,
  X,
} from 'lucide-react';

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import {
  NativeSelect,
  NativeSelectOption,
} from '@/components/ui/native-select';
import { Textarea } from '@/components/ui/textarea';
import {
  api,
  type BudgetCandidate,
  type BudgetSummary,
  type CampaignBrief,
  type RecommendationCandidate,
  type RecommendationResponse,
  type ReviewItem,
  type SelectionReview,
} from '@/lib/api';

const defaultWeights = {
  content_relevance: 0.3,
  audience_fit: 0.2,
  performance: 0.15,
  cost_efficiency: 0.1,
  traffic_quality: 0.1,
  delivery_reliability: 0.1,
  data_quality: 0.05,
};

const dimensionLabels: Record<string, string> = {
  content_relevance: '内容相关性',
  audience_fit: '受众适配度',
  performance: '历史效果',
  cost_efficiency: '成本效率',
  traffic_quality: '流量质量',
  delivery_reliability: '履约能力',
  data_quality: '数据质量',
};

const kpiLabels: Record<string, string> = {
  conversions: '预计转化',
  engagements: '预计互动',
  impressions: '预计曝光',
};

const kpiNouns: Record<string, string> = {
  conversions: '转化',
  engagements: '互动',
  impressions: '曝光',
};

const historyTierLabels: Record<
  RecommendationCandidate['historical_data_availability']['tier'],
  string
> = {
  HISTORY_SUFFICIENT: '历史充分',
  HISTORY_LIMITED: '历史不足',
  COLD_START: '冷启动',
};

const money = new Intl.NumberFormat('zh-CN', {
  style: 'currency',
  currency: 'CNY',
  maximumFractionDigits: 0,
});

function candidateInitial(handle: string) {
  return (
    handle
      .replace(/^[@\s]+/, '')
      .slice(0, 1)
      .toUpperCase() || '达'
  );
}

function statusText(item: ReviewItem) {
  if (item.disposition === 'EXCLUDED') return '已排除';
  if (item.locked) return '人工锁定';
  if (item.source === 'HUMAN') return '人工加入';
  return '系统入选';
}

function MetricCard({
  label,
  value,
  note,
  icon: Icon,
}: {
  label: string;
  value: string;
  note: string;
  icon: typeof Users;
}) {
  return (
    <Card
      size="sm"
      className="border-0 shadow-[0_5px_18px_rgb(24_38_45/4%)] ring-border"
    >
      <CardContent className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs text-muted-foreground">{label}</p>
          <p className="mt-1 truncate font-heading text-xl font-bold tracking-tight">
            {value}
          </p>
          <p className="mt-1 truncate text-[11px] text-muted-foreground">
            {note}
          </p>
        </div>
        <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-muted text-primary">
          <Icon className="size-4" />
        </span>
      </CardContent>
    </Card>
  );
}

function ScoreEvidence({ candidate }: { candidate: RecommendationCandidate }) {
  const scores = candidate.recommendation_reasons
    .map((reason) => {
      const score = Object.entries(reason.evidence_values).find(
        ([key, value]) => key.endsWith('_score') && typeof value === 'number',
      );
      return score
        ? {
            label: dimensionLabels[reason.dimension] ?? reason.dimension,
            value: Number(score[1]) * 100,
          }
        : null;
    })
    .filter((item): item is { label: string; value: number } => item !== null);

  if (!scores.length) return null;
  return (
    <div className="grid gap-x-5 gap-y-3 sm:grid-cols-2 xl:grid-cols-3">
      {scores.map((score) => (
        <div key={score.label}>
          <div className="mb-1.5 flex justify-between text-xs">
            <span>{score.label}</span>
            <span className="font-semibold tabular-nums">
              {score.value.toFixed(1)}
            </span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-primary"
              style={{ width: `${Math.min(score.value, 100)}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

type CreatorCardProps = {
  candidate: RecommendationCandidate;
  item: ReviewItem;
  budgetCandidate?: BudgetCandidate;
  busy: boolean;
  confirmed: boolean;
  onLock: () => void;
  onExclude: () => void;
  onRestore: () => void;
  onInclude: () => void;
  onRiskClear: () => void;
};

function CreatorCard({
  candidate,
  item,
  budgetCandidate,
  busy,
  confirmed,
  onLock,
  onExclude,
  onRestore,
  onInclude,
  onRiskClear,
}: CreatorCardProps) {
  const included = item.disposition === 'INCLUDED';
  const excluded = item.disposition === 'EXCLUDED';
  return (
    <Card
      className={`border-0 transition-shadow ring-border ${included ? 'shadow-[0_12px_34px_rgb(24_38_45/7%)]' : 'bg-card/80'}`}
    >
      <CardContent className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(270px,.58fr)]">
        <div className="min-w-0">
          <div className="flex items-start justify-between gap-4">
            <div className="flex min-w-0 gap-3">
              <span
                className={`grid size-12 shrink-0 place-items-center rounded-2xl font-heading text-base font-bold ${excluded ? 'bg-red-50 text-red-600' : 'bg-[#dce9e4] text-primary'}`}
              >
                {candidateInitial(candidate.handle)}
              </span>
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="truncate font-heading text-base font-bold sm:text-lg">
                    {candidate.handle}
                  </h3>
                  <Badge
                    className={
                      candidate.risk_decision === 'PASS'
                        ? 'bg-emerald-50 text-emerald-700'
                        : 'bg-amber-50 text-amber-700'
                    }
                  >
                    {candidate.risk_decision}
                  </Badge>
                  {included && (
                    <Badge variant="outline">{statusText(item)}</Badge>
                  )}
                  {excluded && <Badge variant="destructive">已排除</Badge>}
                  <Badge variant="secondary">
                    {historyTierLabels[candidate.historical_data_availability.tier]}
                  </Badge>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  {candidate.platform} · 最终排名 #{candidate.final_rank}
                </p>
                <p className="mt-1 text-[11px] text-muted-foreground">
                  有效历史样本量{' '}
                  {candidate.historical_data_availability.effective_history_n.toFixed(2)}
                  {' · '}历史可靠度{' '}
                  {(candidate.historical_data_availability.history_reliability * 100).toFixed(0)}%
                </p>
              </div>
            </div>
            <div className="shrink-0 text-right">
              <p className="font-heading text-2xl font-bold tabular-nums">
                {candidate.fit_score.toFixed(1)}
              </p>
              <p className="text-[10px] tracking-[0.08em] text-muted-foreground">
                FIT SCORE
              </p>
            </div>
          </div>

          <p className="mt-4 rounded-xl bg-muted/65 px-3 py-2.5 text-sm leading-6">
            {candidate.why_this_creator.statement}
          </p>
          <Accordion className="mt-3">
            <AccordionItem value="evidence" className="border-0">
              <AccordionTrigger className="py-1.5 text-xs text-muted-foreground hover:no-underline">
                查看七维评分与数据证据
              </AccordionTrigger>
              <AccordionContent className="pt-3">
                <ScoreEvidence candidate={candidate} />
                <div className="mt-4 space-y-2 border-t border-border pt-3">
                  {candidate.recommendation_reasons.map((reason) => (
                    <p
                      key={reason.dimension}
                      className="text-xs leading-5 text-muted-foreground"
                    >
                      • {reason.statement}
                    </p>
                  ))}
                  {candidate.business_notes.map((note) => (
                    <p
                      key={note}
                      className="text-[11px] leading-5 text-amber-700"
                    >
                      注意：{note}
                    </p>
                  ))}
                </div>
              </AccordionContent>
            </AccordionItem>
          </Accordion>
        </div>

        <div
          className={`rounded-2xl p-4 ${excluded ? 'bg-red-50/80' : included ? 'bg-[#f5efe2]' : 'bg-muted/60'}`}
        >
          <div className="flex items-center justify-between gap-2">
            <p
              className={`text-xs font-bold ${excluded ? 'text-red-700' : 'text-[#775a21]'}`}
            >
              {excluded
                ? '人工处理记录'
                : included
                  ? '达人进入推荐组合原因'
                  : '候选操作'}
            </p>
            {budgetCandidate && (
              <span className="text-xs font-semibold tabular-nums">
                {money.format(budgetCandidate.estimated_cost_cny)}
              </span>
            )}
          </div>
          {excluded ? (
            <p className="mt-2 text-sm leading-6 text-red-800">
              排除原因：{item.reason}
            </p>
          ) : included ? (
            <p className="mt-2 text-sm leading-6 text-[#423823]">
              {budgetCandidate
                ? `${item.locked ? '该达人由人工锁定进入组合' : '该达人由系统组合优化入选'}：预计贡献${kpiNouns[budgetCandidate.primary_kpi] ?? '主KPI'} ${budgetCandidate.expected_primary_kpi.toFixed(2)}，Campaign迁移系数 ${(budgetCandidate.campaign_transfer_factor * 100).toFixed(1)}%，置信修正系数 ${(budgetCandidate.confidence_factor * 100).toFixed(1)}%；与其他入选达人平均受众相似度 ${(budgetCandidate.average_audience_similarity_to_selected * 100).toFixed(1)}%，计入完整重叠代理影响后的估算边际目标贡献约 ${(budgetCandidate.expected_primary_kpi - budgetCandidate.overlap_penalty_contribution * 2).toFixed(2)}。`
                : '该达人已被人工加入，等待组合重新计算。'}
            </p>
          ) : (
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              未进入当前组合。可人工加入并锁定，系统会在保留该达人的前提下重新优化其余名额。
            </p>
          )}

          {candidate.risk_decision === 'REVIEW' &&
            item.risk_resolution !== 'CLEARED' &&
            !excluded && (
              <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs leading-5 text-amber-800">
                该达人需先完成风险复核，才可人工加入最终组合。
                <Button
                  disabled={busy || confirmed}
                  onClick={onRiskClear}
                  variant="outline"
                  size="sm"
                  className="mt-2 border-amber-300 bg-white"
                >
                  标记已复核通过
                </Button>
              </div>
            )}
          {item.risk_resolution === 'CLEARED' && (
            <p className="mt-3 flex items-center gap-1.5 text-xs font-medium text-emerald-700">
              <ShieldCheck className="size-3.5" />
              风险已人工复核通过
            </p>
          )}

          <div className="mt-4 flex flex-wrap gap-2">
            {included && (
              <Button
                disabled={busy || confirmed}
                size="sm"
                variant="outline"
                onClick={onLock}
              >
                {item.locked ? <LockOpen /> : <Lock />}
                {item.locked ? '解除锁定' : '锁定达人'}
              </Button>
            )}
            {!included && !excluded && (
              <Button
                disabled={
                  busy ||
                  confirmed ||
                  (candidate.risk_decision === 'REVIEW' &&
                    item.risk_resolution !== 'CLEARED')
                }
                size="sm"
                onClick={onInclude}
              >
                <UserPlus />
                人工加入
              </Button>
            )}
            {!excluded && (
              <Button
                disabled={busy || confirmed}
                size="sm"
                variant="destructive"
                onClick={onExclude}
              >
                <X />
                排除
              </Button>
            )}
            {excluded && (
              <Button
                disabled={busy || confirmed}
                size="sm"
                variant="outline"
                onClick={onRestore}
              >
                <Undo2 />
                恢复候选
              </Button>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default function Home() {
  const [briefs, setBriefs] = useState<CampaignBrief[]>([]);
  const [campaignId, setCampaignId] = useState('cmp_0001');
  const [query, setQuery] = useState('配料表');
  const [candidateCount, setCandidateCount] = useState(20);
  const [keywordWeight, setKeywordWeight] = useState(0.5);
  const [vectorWeight, setVectorWeight] = useState(0.5);
  const [retrievalDepth, setRetrievalDepth] = useState(100);
  const [rrfK, setRrfK] = useState(60);
  const [fitMode, setFitMode] = useState<'default' | 'custom'>('default');
  const [weights, setWeights] = useState(defaultWeights);
  const [recommendation, setRecommendation] =
    useState<RecommendationResponse | null>(null);
  const [review, setReview] = useState<SelectionReview | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionBusy, setActionBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [excludeTarget, setExcludeTarget] =
    useState<RecommendationCandidate | null>(null);
  const [excludeReason, setExcludeReason] = useState('');
  const [confirmOpen, setConfirmOpen] = useState(false);

  const currentBrief = briefs.find((brief) => brief.campaign_id === campaignId);
  const budget: BudgetSummary | null =
    review?.optimization_summary ?? recommendation?.budget_optimization ?? null;
  const reviewByAccount = useMemo(
    () => new Map(review?.items.map((item) => [item.account_id, item]) ?? []),
    [review],
  );
  const budgetByAccount = useMemo(
    () =>
      new Map(
        budget?.selected_candidates.map((item) => [item.account_id, item]) ??
          [],
      ),
    [budget],
  );
  const includedCandidates =
    recommendation?.candidates.filter(
      (candidate) =>
        reviewByAccount.get(candidate.account_id)?.disposition === 'INCLUDED',
    ) ?? [];
  const otherCandidates =
    recommendation?.candidates.filter(
      (candidate) =>
        reviewByAccount.get(candidate.account_id)?.disposition !== 'INCLUDED',
    ) ?? [];
  const confirmed = review?.status === 'CONFIRMED';

  async function runRecommendation(selectedCampaign = campaignId) {
    setLoading(true);
    setError(null);
    setNotice(null);
    try {
      const fit =
        fitMode === 'default'
          ? { mode: 'default' }
          : { mode: 'custom', weights };
      const result = await api.recommend({
        campaign_id: selectedCampaign,
        query,
        candidate_count: candidateCount,
        retrieval_advanced: {
          keyword_weight: keywordWeight,
          vector_weight: vectorWeight,
          retrieval_depth: Math.max(retrievalDepth, candidateCount),
          rrf_k: rrfK,
        },
        fit,
      });
      const reviewResult = await api.createReview(
        result.recommendation_run_id,
        '业务审核员',
      );
      setRecommendation(result);
      setReview(reviewResult);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '无法生成推荐结果');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const items = await api.listBriefs();
        if (!active) return;
        setBriefs(items);
        const initial = items.some((item) => item.campaign_id === 'cmp_0001')
          ? 'cmp_0001'
          : items[0]?.campaign_id;
        if (!initial) {
          setLoading(false);
          setError('尚无可用的Campaign Brief。');
          return;
        }
        setCampaignId(initial);
        const result = await api.recommend({
          campaign_id: initial,
          query: '配料表',
          candidate_count: 20,
          retrieval_advanced: {
            keyword_weight: 0.5,
            vector_weight: 0.5,
            retrieval_depth: 100,
            rrf_k: 60,
          },
          fit: { mode: 'default' },
        });
        const reviewResult = await api.createReview(
          result.recommendation_run_id,
          '业务审核员',
        );
        if (!active) return;
        setRecommendation(result);
        setReview(reviewResult);
        setLoading(false);
      } catch (cause) {
        if (!active) return;
        setLoading(false);
        setError(cause instanceof Error ? cause.message : '无法读取Campaign');
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!review || review.status === 'CONFIRMED') return;
    type ModelContext = {
      registerTool: (
        tool: {
          name: string;
          title: string;
          description: string;
          inputSchema: Record<string, unknown>;
          annotations: { readOnlyHint: boolean; untrustedContentHint: boolean };
          execute: () => Promise<Record<string, unknown>>;
        },
        options: { signal: AbortSignal },
      ) => unknown;
    };
    const context = (document as Document & { modelContext?: ModelContext })
      .modelContext;
    if (!context?.registerTool) return;
    const lifecycle = new AbortController();
    const options = { signal: lifecycle.signal };
    void Promise.resolve(
      context.registerTool(
        {
          name: 'recalculate_creator_portfolio',
          title: '重新优化达人组合',
          description:
            '保留页面上已锁定和已排除的人工决策，重新计算剩余达人组合。',
          inputSchema: {
            type: 'object',
            properties: {},
            additionalProperties: false,
          },
          annotations: { readOnlyHint: false, untrustedContentHint: false },
          async execute() {
            const updated = await api.recalculate(
              review.review_id,
              '业务审核员',
            );
            setReview(updated);
            setNotice('已按人工约束重新优化组合。');
            return {
              reviewId: updated.review_id,
              selectedCount:
                updated.optimization_summary.selected_creator_count,
              status: updated.status,
            };
          },
        },
        options,
      ),
    ).catch(() => undefined);
    void Promise.resolve(
      context.registerTool(
        {
          name: 'confirm_final_creator_selection',
          title: '确认最终达人名单',
          description:
            '确认当前最终组合并锁定本次人工审核，操作将写入审计记录。',
          inputSchema: {
            type: 'object',
            properties: {},
            additionalProperties: false,
          },
          annotations: { readOnlyHint: false, untrustedContentHint: false },
          async execute() {
            const updated = await api.confirm(review.review_id, '业务审核员');
            setReview(updated);
            setNotice('最终名单已确认并写入审计记录。');
            return {
              reviewId: updated.review_id,
              selectedCount:
                updated.optimization_summary.selected_creator_count,
              status: updated.status,
            };
          },
        },
        options,
      ),
    ).catch(() => undefined);
    return () => lifecycle.abort();
  }, [review]);

  async function mutateItem(
    accountId: string,
    payload: Record<string, unknown>,
    recalculate = false,
  ) {
    if (!review) return;
    setActionBusy(true);
    setError(null);
    try {
      const updated = await api.updateReviewItem(review.review_id, accountId, {
        ...payload,
        actor_name: '业务审核员',
      });
      const finalReview = recalculate
        ? await api.recalculate(updated.review_id, '业务审核员')
        : updated;
      setReview(finalReview);
      setNotice(recalculate ? '已按人工约束重新优化组合。' : '操作已保存。');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '操作失败');
    } finally {
      setActionBusy(false);
    }
  }

  async function confirmSelection() {
    if (!review) return;
    setActionBusy(true);
    try {
      const result = await api.confirm(review.review_id, '业务审核员');
      setReview(result);
      setConfirmOpen(false);
      setNotice('最终名单已确认并写入审计记录。');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '提交失败');
      setConfirmOpen(false);
    } finally {
      setActionBusy(false);
    }
  }

  async function excludeCreator() {
    if (!excludeTarget || !excludeReason.trim()) return;
    await mutateItem(
      excludeTarget.account_id,
      { action: 'exclude', reason: excludeReason },
      true,
    );
    setExcludeTarget(null);
    setExcludeReason('');
  }

  const fitWeightTotal = Object.values(weights).reduce(
    (sum, value) => sum + value,
    0,
  );
  const allWarnings = [
    ...(recommendation?.warnings.map((warning) => warning.message) ?? []),
    ...(budget?.warnings.filter(
      (warning) => !warning.includes('audience_overlap'),
    ) ?? []),
  ];

  return (
    <main className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-20 border-b border-border/80 bg-background/92 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-[1480px] items-center justify-between px-5 lg:px-8">
          <div className="flex items-center gap-3">
            <span className="grid size-9 place-items-center rounded-xl bg-primary text-primary-foreground">
              <Sparkles className="size-4" />
            </span>
            <div>
              <div className="font-heading text-sm font-bold">MatchBridge 智选</div>
              <div className="text-[10px] tracking-[0.18em] text-muted-foreground">
                CAMPAIGN-CREATOR MATCH
              </div>
            </div>
          </div>
          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            {review && (
              <span className="hidden sm:inline">
                审计版本 v{review.version}
              </span>
            )}
            <Badge
              className={
                confirmed
                  ? 'bg-emerald-50 text-emerald-700'
                  : 'bg-amber-50 text-amber-700'
              }
            >
              {confirmed ? '名单已确认' : '等待人工确认'}
            </Badge>
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-[1480px] gap-6 px-5 py-7 lg:grid-cols-[220px_minmax(0,1fr)] lg:px-8">
        <aside className="hidden lg:block">
          <nav className="space-y-1 text-sm">
            <div className="mb-4 px-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
              选号流程
            </div>
            <a
              className="flex items-center gap-3 rounded-xl bg-primary px-3 py-2.5 text-primary-foreground"
              href="#workspace"
            >
              <LayoutGrid className="size-4" />
              选号工作台
            </a>
            <a
              className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-muted-foreground hover:bg-muted"
              href="#candidates"
            >
              <Users className="size-4" />
              全部候选
            </a>
            <a
              className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-muted-foreground hover:bg-muted"
              href="#warnings"
            >
              <ShieldAlert className="size-4" />
              风险与提醒
            </a>
          </nav>
          <div className="mt-8 rounded-2xl border border-border bg-card p-4">
            <div className="flex items-center gap-2 text-xs font-semibold">
              <CheckCircle2
                className={`size-4 ${confirmed ? 'text-emerald-600' : 'text-amber-600'}`}
              />
              当前进度
            </div>
            <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-muted">
              <div
                className={`h-full rounded-full ${confirmed ? 'w-full bg-emerald-500' : 'w-4/5 bg-accent'}`}
              />
            </div>
            <p className="mt-2 text-xs leading-5 text-muted-foreground">
              {confirmed
                ? '最终名单已确认，人工操作均已留痕。'
                : '系统组合已生成，请复核、调整并提交。'}
            </p>
          </div>
        </aside>

        <section id="workspace" className="min-w-0">
          <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
            <div>
              <p className="text-xs font-semibold text-[#8b6424]">
                CAMPAIGN / {campaignId}
              </p>
              <h1 className="mt-1 font-heading text-3xl font-bold tracking-[-0.035em]">
                {currentBrief
                  ? `${currentBrief.product_name}达人选号`
                  : '达人选号工作台'}
              </h1>
              <p className="mt-2 text-sm text-muted-foreground">
                {currentBrief
                  ? `${currentBrief.brand_name} · ${currentBrief.product_category} · ${currentBrief.target_platforms.join(' / ')}`
                  : '加载Campaign信息中'}
              </p>
            </div>
            <Button
              disabled={!review || loading || confirmed}
              className="h-10 rounded-xl px-4"
              onClick={() => setConfirmOpen(true)}
            >
              {confirmed ? <Check /> : <ArrowRight />}
              {confirmed ? '名单已确认' : '提交最终名单'}
            </Button>
          </div>

          <Card className="mt-6 border-0 bg-card shadow-[0_12px_36px_rgb(24_38_45/6%)] ring-border">
            <CardContent className="grid gap-4 md:grid-cols-[210px_minmax(220px,1fr)_120px_auto] md:items-end">
              <label
                htmlFor="campaign-select"
                className="grid gap-2 text-xs font-semibold"
              >
                Campaign
                <NativeSelect
                  value={campaignId}
                  id="campaign-select"
                  onChange={(event) => setCampaignId(event.target.value)}
                  className="w-full"
                >
                  <NativeSelectOption value="" disabled>
                    选择Campaign
                  </NativeSelectOption>
                  {briefs.map((brief) => (
                    <NativeSelectOption
                      key={brief.campaign_id}
                      value={brief.campaign_id}
                    >
                      {brief.campaign_id} · {brief.product_name}
                    </NativeSelectOption>
                  ))}
                </NativeSelect>
              </label>
              <label
                htmlFor="focus-query"
                className="grid gap-2 text-xs font-semibold"
              >
                本次关注点
                <div className="relative">
                  <Search className="absolute left-3 top-3 size-4 text-muted-foreground" />
                  <Input
                    value={query}
                    id="focus-query"
                    onChange={(event) => setQuery(event.target.value)}
                    className="h-10 bg-background pl-9"
                  />
                </div>
              </label>
              <label
                htmlFor="candidate-count"
                className="grid gap-2 text-xs font-semibold"
              >
                候选人数
                <Input
                  type="number"
                  id="candidate-count"
                  min={1}
                  max={200}
                  value={candidateCount}
                  onChange={(event) =>
                    setCandidateCount(Number(event.target.value))
                  }
                  className="h-10 bg-background"
                />
              </label>
              <Button
                disabled={
                  loading ||
                  !campaignId ||
                  !query.trim() ||
                  (fitMode === 'custom' &&
                    Math.abs(fitWeightTotal - 1) > 0.000001)
                }
                onClick={() => void runRecommendation()}
                className="h-10 rounded-xl bg-accent px-5 text-accent-foreground hover:bg-accent/85"
              >
                {loading ? <Loader2 className="animate-spin" /> : <RefreshCw />}
                生成推荐
              </Button>
              <details className="group md:col-span-4">
                <summary className="flex cursor-pointer list-none items-center gap-1 text-xs font-medium text-muted-foreground">
                  <SlidersHorizontal className="size-3.5" />
                  高级设置
                  <ChevronDown className="size-3 transition-transform group-open:rotate-180" />
                </summary>
                <div className="mt-4 grid gap-5 rounded-xl border border-border bg-background/70 p-4 lg:grid-cols-2">
                  <div>
                    <p className="mb-3 text-xs font-bold">Hybrid召回</p>
                    <div className="grid grid-cols-2 gap-3">
                      {[
                        ['关键词权重', keywordWeight, setKeywordWeight],
                        ['内容契合权重', vectorWeight, setVectorWeight],
                        ['召回深度', retrievalDepth, setRetrievalDepth],
                        ['RRF平滑参数', rrfK, setRrfK],
                      ].map(([label, value, setter]) => (
                        <label
                          key={String(label)}
                          className="grid gap-1.5 text-[11px] text-muted-foreground"
                        >
                          {String(label)}
                          <Input
                            type="number"
                            step={String(label).includes('权重') ? 0.05 : 1}
                            value={Number(value)}
                            onChange={(event) =>
                              (setter as (value: number) => void)(
                                Number(event.target.value),
                              )
                            }
                          />
                        </label>
                      ))}
                    </div>
                  </div>
                  <div>
                    <div className="mb-3 flex items-center justify-between">
                      <p className="text-xs font-bold">Fit七维权重</p>
                      <NativeSelect
                        size="sm"
                        value={fitMode}
                        onChange={(event) =>
                          setFitMode(event.target.value as 'default' | 'custom')
                        }
                      >
                        <NativeSelectOption value="default">
                          默认
                        </NativeSelectOption>
                        <NativeSelectOption value="custom">
                          自定义
                        </NativeSelectOption>
                      </NativeSelect>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      {Object.entries(weights).map(([name, value]) => (
                        <label
                          key={name}
                          className="flex items-center justify-between gap-2 text-[11px] text-muted-foreground"
                        >
                          <span>{dimensionLabels[name]}</span>
                          <Input
                            disabled={fitMode === 'default'}
                            type="number"
                            min={0}
                            max={1}
                            step={0.05}
                            value={value}
                            onChange={(event) =>
                              setWeights((current) => ({
                                ...current,
                                [name]: Number(event.target.value),
                              }))
                            }
                            className="w-20"
                          />
                        </label>
                      ))}
                    </div>
                    <p
                      className={`mt-2 text-right text-[11px] ${Math.abs(fitWeightTotal - 1) < 0.000001 ? 'text-emerald-700' : 'text-red-600'}`}
                    >
                      权重合计 {(fitWeightTotal * 100).toFixed(0)}%
                    </p>
                  </div>
                </div>
              </details>
            </CardContent>
          </Card>

          {error && (
            <div className="mt-4 flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">
              <AlertTriangle className="mt-0.5 size-4 shrink-0" />
              {error}
            </div>
          )}
          {notice && (
            <div className="mt-4 flex items-start gap-2 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">
              <CheckCircle2 className="mt-0.5 size-4 shrink-0" />
              {notice}
            </div>
          )}

          {loading && !recommendation ? (
            <div className="grid min-h-[420px] place-items-center">
              <div className="text-center">
                <Loader2 className="mx-auto size-7 animate-spin text-primary" />
                <p className="mt-3 text-sm text-muted-foreground">
                  正在检索、评分并优化组合…
                </p>
              </div>
            </div>
          ) : budget && recommendation && review ? (
            <>
              <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <MetricCard
                  label="最终组合"
                  value={`${budget.selected_creator_count} / ${budget.target_creator_count} 位`}
                  note={
                    budget.staffing_status === 'FULL'
                      ? '达到Brief目标人数'
                      : '当前为部分组合'
                  }
                  icon={Users}
                />
                <MetricCard
                  label="组合报价"
                  value={money.format(budget.selected_total_cost_cny)}
                  note={`剩余 ${money.format(budget.remaining_budget_cny)}`}
                  icon={CircleDollarSign}
                />
                <MetricCard
                  label={kpiLabels[budget.primary_kpi] ?? '预计主KPI'}
                  value={budget.selected_total_expected_primary_kpi.toFixed(2)}
                  note={`重叠修正后 ${budget.overlap_adjusted_expected_primary_kpi.toFixed(2)}`}
                  icon={Sparkles}
                />
                <MetricCard
                  label="人工确认"
                  value={
                    confirmed
                      ? '已完成'
                      : `${includedCandidates.filter((candidate) => reviewByAccount.get(candidate.account_id)?.locked).length} 位锁定`
                  }
                  note={`审计版本 v${review.version}`}
                  icon={FileClock}
                />
              </div>

              <section className="mt-5 rounded-2xl border border-border bg-card p-4 shadow-[0_5px_18px_rgb(24_38_45/4%)]">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <h2 className="text-sm font-bold">历史数据情况</h2>
                    <p className="mt-1 text-xs text-muted-foreground">
                      根据本次Campaign可用的历史合作数据，对候选达人进行分类。
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(historyTierLabels).map(([tier, label]) => (
                      <Badge key={tier} variant="outline">
                        {label}{' '}
                        {recommendation.candidates.filter(
                          (candidate) =>
                            candidate.historical_data_availability.tier === tier,
                        ).length}
                      </Badge>
                    ))}
                  </div>
                </div>
              </section>

              {allWarnings.length > 0 && (
                <section
                  id="warnings"
                  className="mt-5 rounded-2xl border border-amber-200 bg-amber-50/80 p-4"
                >
                  <div className="flex items-center gap-2 text-sm font-bold text-amber-900">
                    <AlertTriangle className="size-4" />
                    运行提醒
                  </div>
                  <ul className="mt-2 space-y-1.5 text-xs leading-5 text-amber-800">
                    {allWarnings.map((warning) => (
                      <li key={warning}>• {warning}</li>
                    ))}
                  </ul>
                </section>
              )}

              <div className="mt-8 flex items-end justify-between">
                <div>
                  <h2 className="font-heading text-xl font-bold">
                    最终推荐组合
                  </h2>
                  <p className="mt-1 text-xs text-muted-foreground">
                    锁定达人不会在重新计算时被移出 · 受众重叠为代理估计
                  </p>
                </div>
                <Badge variant="outline">{includedCandidates.length} 位</Badge>
              </div>
              <div className="mt-4 space-y-4">
                {includedCandidates.map((candidate) => {
                  const item = reviewByAccount.get(candidate.account_id)!;
                  return (
                    <CreatorCard
                      key={candidate.account_id}
                      candidate={candidate}
                      item={item}
                      budgetCandidate={budgetByAccount.get(
                        candidate.account_id,
                      )}
                      busy={actionBusy}
                      confirmed={confirmed}
                      onLock={() =>
                        void mutateItem(candidate.account_id, {
                          action: 'set_lock',
                          locked: !item.locked,
                        })
                      }
                      onExclude={() => setExcludeTarget(candidate)}
                      onRestore={() =>
                        void mutateItem(
                          candidate.account_id,
                          { action: 'restore' },
                          true,
                        )
                      }
                      onInclude={() =>
                        void mutateItem(
                          candidate.account_id,
                          { action: 'include', locked: true },
                          true,
                        )
                      }
                      onRiskClear={() =>
                        void mutateItem(candidate.account_id, {
                          action: 'resolve_risk',
                          risk_resolution: 'CLEARED',
                          reason: '人工复核通过',
                        })
                      }
                    />
                  );
                })}
              </div>

              <section id="candidates" className="mt-10">
                <div className="flex items-end justify-between">
                  <div>
                    <h2 className="font-heading text-xl font-bold">
                      其他候选人
                    </h2>
                    <p className="mt-1 text-xs text-muted-foreground">
                      可人工加入、排除或完成风险复核
                    </p>
                  </div>
                  <Badge variant="secondary">{otherCandidates.length} 位</Badge>
                </div>
                <div className="mt-4 space-y-4">
                  {otherCandidates.map((candidate) => {
                    const item = reviewByAccount.get(candidate.account_id)!;
                    return (
                      <CreatorCard
                        key={candidate.account_id}
                        candidate={candidate}
                        item={item}
                        budgetCandidate={budgetByAccount.get(
                          candidate.account_id,
                        )}
                        busy={actionBusy}
                        confirmed={confirmed}
                        onLock={() =>
                          void mutateItem(candidate.account_id, {
                            action: 'set_lock',
                            locked: !item.locked,
                          })
                        }
                        onExclude={() => setExcludeTarget(candidate)}
                        onRestore={() =>
                          void mutateItem(
                            candidate.account_id,
                            { action: 'restore' },
                            true,
                          )
                        }
                        onInclude={() =>
                          void mutateItem(
                            candidate.account_id,
                            { action: 'include', locked: true },
                            true,
                          )
                        }
                        onRiskClear={() =>
                          void mutateItem(candidate.account_id, {
                            action: 'resolve_risk',
                            risk_resolution: 'CLEARED',
                            reason: '人工复核通过',
                          })
                        }
                      />
                    );
                  })}
                </div>
              </section>
            </>
          ) : null}
        </section>
      </div>

      <Dialog
        open={excludeTarget !== null}
        onOpenChange={(open) => {
          if (!open) {
            setExcludeTarget(null);
            setExcludeReason('');
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>排除{excludeTarget?.handle}</DialogTitle>
            <DialogDescription>
              排除原因将写入人工选号审计记录。系统会保留其他锁定达人并重新优化剩余名额。
            </DialogDescription>
          </DialogHeader>
          <Textarea
            value={excludeReason}
            onChange={(event) => setExcludeReason(event.target.value)}
            placeholder="例如：近期内容调性与品牌不符"
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setExcludeTarget(null)}>
              取消
            </Button>
            <Button
              variant="destructive"
              disabled={!excludeReason.trim() || actionBusy}
              onClick={() => void excludeCreator()}
            >
              {actionBusy && <Loader2 className="animate-spin" />}确认排除并重算
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>确认提交最终达人名单？</DialogTitle>
            <DialogDescription>
              提交后本次审核将锁定为只读状态。最终组合、人工排除、风险复核和操作人都会保留在审计记录中。
            </DialogDescription>
          </DialogHeader>
          <div className="rounded-xl bg-muted p-3 text-sm">
            <div className="flex justify-between">
              <span>入选达人</span>
              <strong>{includedCandidates.length} 位</strong>
            </div>
            <div className="mt-2 flex justify-between">
              <span>组合报价</span>
              <strong>
                {budget ? money.format(budget.selected_total_cost_cny) : '—'}
              </strong>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmOpen(false)}>
              返回检查
            </Button>
            <Button
              disabled={actionBusy || includedCandidates.length === 0}
              onClick={() => void confirmSelection()}
            >
              {actionBusy ? <Loader2 className="animate-spin" /> : <Check />}
              确认并提交
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </main>
  );
}
