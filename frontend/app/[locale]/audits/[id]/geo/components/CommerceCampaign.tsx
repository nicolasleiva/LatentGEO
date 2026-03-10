"use client";

import { useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  Blocks,
  Bot,
  ExternalLink,
  Search,
  ShoppingBag,
  Sparkles,
  Target,
  TrendingUp,
  Trophy,
  Zap,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { fetchWithBackendAuth } from "@/lib/backend-auth";

interface CommerceResultItem {
  position: number;
  title: string;
  url: string;
  domain: string;
  snippet: string;
}

interface CommerceGapItem {
  area: string;
  gap: string;
  impact: string;
}

interface CommerceActionItem {
  priority: string;
  action: string;
  expected_impact: string;
  evidence: string;
}

interface CommerceEvidenceItem {
  title: string;
  url: string;
}

interface CommerceRootSummary {
  path: string;
  url: string;
  overall_score: number | null;
  schema_score: number | null;
  content_score: number | null;
  h1_score: number | null;
  critical_issues: number | null;
  high_issues: number | null;
}

interface CommerceRootCauseItem {
  title: string;
  finding: string;
  owner: string;
}

interface CommerceTechnicalWatchout {
  priority: string;
  owner: string;
  action: string;
  evidence: string;
}

interface CommerceProductIntelligence {
  is_ecommerce: boolean;
  confidence_score: number | null;
  platform: string;
  product_pages_count: number | null;
  category_pages_count: number | null;
  schema_analysis?: {
    average_completeness?: number | null;
    schema_coverage_percent?: number | null;
  };
}

interface CommerceQueryAnalysis {
  analysis_id?: number;
  query: string;
  market: string;
  audited_domain: string;
  target_position: number | null;
  top_result: CommerceResultItem | null;
  results: CommerceResultItem[];
  why_not_first: string[];
  disadvantages_vs_top1: CommerceGapItem[];
  action_plan: CommerceActionItem[];
  site_root_summary: CommerceRootSummary | null;
  root_cause_summary: CommerceRootCauseItem[];
  search_engine_fixes: CommerceActionItem[];
  merchandising_fixes: CommerceActionItem[];
  technical_watchouts: CommerceTechnicalWatchout[];
  product_intelligence: CommerceProductIntelligence | null;
  evidence: CommerceEvidenceItem[];
  provider?: string;
}

interface CommerceCampaignProps {
  auditId: number;
  backendUrl: string;
}

const DEFAULT_TOP_K = 10;

const toNonEmptyString = (value: unknown, fallback = ""): string => {
  if (typeof value === "string" && value.trim()) return value.trim();
  return fallback;
};

const toNumberOrNull = (value: unknown): number | null => {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return null;
};

const normalizeResultItem = (
  item: any,
  index: number,
): CommerceResultItem | null => {
  if (!item || typeof item !== "object") return null;
  const url = toNonEmptyString(item.url);
  const domain = toNonEmptyString(item.domain);
  if (!url || !domain) return null;
  return {
    position: toNumberOrNull(item.position) ?? index + 1,
    title: toNonEmptyString(item.title, domain),
    url,
    domain,
    snippet: toNonEmptyString(item.snippet),
  };
};

const normalizeActionItems = (items: any): CommerceActionItem[] =>
  Array.isArray(items)
    ? items
        .map((item: any) => ({
          priority: toNonEmptyString(item?.priority, "P2"),
          action: toNonEmptyString(item?.action),
          expected_impact: toNonEmptyString(item?.expected_impact, "Medium"),
          evidence: toNonEmptyString(item?.evidence),
        }))
        .filter((item: CommerceActionItem) => item.action.length > 0)
    : [];

const normalizeAnalysis = (payload: any): CommerceQueryAnalysis | null => {
  if (!payload || typeof payload !== "object") return null;

  const results = Array.isArray(payload.results)
    ? payload.results
        .map((item: any, index: number) => normalizeResultItem(item, index))
        .filter((item: CommerceResultItem | null): item is CommerceResultItem =>
          Boolean(item),
        )
    : [];

  const topResult = normalizeResultItem(payload.top_result, 0);

  return {
    analysis_id: toNumberOrNull(payload.analysis_id) ?? undefined,
    query: toNonEmptyString(payload.query),
    market: toNonEmptyString(payload.market),
    audited_domain: toNonEmptyString(payload.audited_domain),
    target_position: toNumberOrNull(payload.target_position),
    top_result: topResult,
    results,
    why_not_first: Array.isArray(payload.why_not_first)
      ? payload.why_not_first
          .map((item: any) => toNonEmptyString(item))
          .filter(Boolean)
      : [],
    disadvantages_vs_top1: Array.isArray(payload.disadvantages_vs_top1)
      ? payload.disadvantages_vs_top1
          .map((item: any) => ({
            area: toNonEmptyString(item?.area, "Gap"),
            gap: toNonEmptyString(item?.gap),
            impact: toNonEmptyString(item?.impact),
          }))
          .filter((item: CommerceGapItem) => item.gap.length > 0)
      : [],
    action_plan: normalizeActionItems(payload.action_plan),
    site_root_summary:
      payload.site_root_summary && typeof payload.site_root_summary === "object"
        ? {
            path: toNonEmptyString(payload.site_root_summary.path, "/"),
            url: toNonEmptyString(payload.site_root_summary.url),
            overall_score: toNumberOrNull(
              payload.site_root_summary.overall_score,
            ),
            schema_score: toNumberOrNull(
              payload.site_root_summary.schema_score,
            ),
            content_score: toNumberOrNull(
              payload.site_root_summary.content_score,
            ),
            h1_score: toNumberOrNull(payload.site_root_summary.h1_score),
            critical_issues: toNumberOrNull(
              payload.site_root_summary.critical_issues,
            ),
            high_issues: toNumberOrNull(payload.site_root_summary.high_issues),
          }
        : null,
    root_cause_summary: Array.isArray(payload.root_cause_summary)
      ? payload.root_cause_summary
          .map((item: any) => ({
            title: toNonEmptyString(item?.title, "Root cause"),
            finding: toNonEmptyString(item?.finding),
            owner: toNonEmptyString(item?.owner, "SEO / Product"),
          }))
          .filter((item: CommerceRootCauseItem) => item.finding.length > 0)
      : [],
    search_engine_fixes: normalizeActionItems(payload.search_engine_fixes),
    merchandising_fixes: normalizeActionItems(payload.merchandising_fixes),
    technical_watchouts: Array.isArray(payload.technical_watchouts)
      ? payload.technical_watchouts
          .map((item: any) => ({
            priority: toNonEmptyString(item?.priority, "Medium"),
            owner: toNonEmptyString(item?.owner, "Frontend / SEO"),
            action: toNonEmptyString(item?.action),
            evidence: toNonEmptyString(item?.evidence),
          }))
          .filter((item: CommerceTechnicalWatchout) => item.action.length > 0)
      : [],
    product_intelligence:
      payload.product_intelligence &&
      typeof payload.product_intelligence === "object"
        ? {
            is_ecommerce: Boolean(payload.product_intelligence.is_ecommerce),
            confidence_score: toNumberOrNull(
              payload.product_intelligence.confidence_score,
            ),
            platform: toNonEmptyString(payload.product_intelligence.platform),
            product_pages_count: toNumberOrNull(
              payload.product_intelligence.product_pages_count,
            ),
            category_pages_count: toNumberOrNull(
              payload.product_intelligence.category_pages_count,
            ),
            schema_analysis:
              payload.product_intelligence.schema_analysis &&
              typeof payload.product_intelligence.schema_analysis === "object"
                ? {
                    average_completeness: toNumberOrNull(
                      payload.product_intelligence.schema_analysis
                        .average_completeness,
                    ),
                    schema_coverage_percent: toNumberOrNull(
                      payload.product_intelligence.schema_analysis
                        .schema_coverage_percent,
                    ),
                  }
                : undefined,
          }
        : null,
    evidence: Array.isArray(payload.evidence)
      ? payload.evidence
          .map((item: any) => ({
            title: toNonEmptyString(
              item?.title,
              toNonEmptyString(item?.url, "Source"),
            ),
            url: toNonEmptyString(item?.url),
          }))
          .filter((item: CommerceEvidenceItem) => item.url.length > 0)
      : [],
    provider: toNonEmptyString(payload.provider),
  };
};

function ActionBlock({
  title,
  icon,
  items,
  emptyMessage,
}: {
  title: string;
  icon: React.ReactNode;
  items: CommerceActionItem[];
  emptyMessage: string;
}) {
  return (
    <div className="bg-muted/30 border border-border rounded-xl p-6">
      <h3 className="font-semibold text-foreground text-xl mb-3 flex items-center gap-2">
        {icon}
        {title}
      </h3>
      {items.length > 0 ? (
        <div className="space-y-3">
          {items.map((step, idx) => (
            <div
              key={`${title}-${idx}`}
              className="border border-border rounded-lg p-4 bg-muted/40"
            >
              <div className="flex items-center gap-2">
                <span className="px-2 py-1 rounded-md text-xs border border-brand/30 bg-brand/10 text-foreground">
                  {step.priority}
                </span>
                <span className="text-xs text-muted-foreground">
                  Impact: {step.expected_impact}
                </span>
              </div>
              <p className="text-sm text-foreground mt-2">{step.action}</p>
              {step.evidence ? (
                <p className="text-xs text-muted-foreground mt-2">
                  Evidence: {step.evidence}
                </p>
              ) : null}
            </div>
          ))}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">{emptyMessage}</p>
      )}
    </div>
  );
}

export default function CommerceCampaign({
  auditId,
  backendUrl,
}: CommerceCampaignProps) {
  const [query, setQuery] = useState("");
  const [market, setMarket] = useState("AR");
  const [language, setLanguage] = useState("es");
  const [topK, setTopK] = useState(DEFAULT_TOP_K);
  const [result, setResult] = useState<CommerceQueryAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingLatest, setLoadingLatest] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadLatest = async () => {
      setLoadingLatest(true);
      try {
        const res = await fetchWithBackendAuth(
          `${backendUrl}/api/v1/geo/commerce-query/latest/${auditId}`,
        );
        if (!res.ok) {
          throw new Error(`Failed to fetch latest analysis (${res.status})`);
        }
        const data = await res.json();
        if (data?.has_data) {
          const normalized = normalizeAnalysis(data);
          if (normalized) {
            setResult(normalized);
            if (normalized.query) setQuery(normalized.query);
            if (normalized.market) setMarket(normalized.market);
          }
        }
      } catch (err: any) {
        setError(err?.message || "Failed to load latest analysis");
      } finally {
        setLoadingLatest(false);
      }
    };
    loadLatest();
  }, [auditId, backendUrl]);

  const rankMessage = useMemo(() => {
    if (!result) return "";
    if (result.target_position === null) return `Not ranking in top ${topK}`;
    if (result.target_position === 1) return "Ranking #1";
    return `Ranking #${result.target_position}`;
  }, [result, topK]);

  const platformLabel = useMemo(() => {
    const value = result?.product_intelligence?.platform || "unknown";
    return value.replace(/_/g, " ");
  }, [result?.product_intelligence?.platform]);

  const analyzeQuery = async () => {
    const safeQuery = query.trim();
    const safeMarket = market.trim().toUpperCase();
    if (!safeQuery || !safeMarket) {
      setError("Query and market are required.");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const res = await fetchWithBackendAuth(
        `${backendUrl}/api/v1/geo/commerce-query/analyze`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            audit_id: auditId,
            query: safeQuery,
            market: safeMarket,
            top_k: topK,
            language,
          }),
        },
      );

      const responseText = await res.text();
      let parsed: any = {};
      try {
        parsed = responseText ? JSON.parse(responseText) : {};
      } catch {
        parsed = { detail: responseText };
      }
      if (!res.ok) {
        throw new Error(parsed?.detail || `Analysis failed (${res.status})`);
      }

      const normalized = normalizeAnalysis(parsed);
      if (!normalized) {
        throw new Error("Invalid analysis payload");
      }

      setResult(normalized);
    } catch (err: any) {
      setError(err?.message || "Failed to analyze query");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-muted/30 border border-border rounded-xl p-6 space-y-4">
        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <Label className="text-muted-foreground">Query</Label>
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="zapatilla nike"
              className="mt-2 bg-muted/30 border-border/70 text-foreground"
            />
          </div>
          <div>
            <Label className="text-muted-foreground">Market</Label>
            <Input
              value={market}
              onChange={(e) => setMarket(e.target.value.toUpperCase())}
              placeholder="AR, US, MX"
              className="mt-2 bg-muted/30 border-border/70 text-foreground"
            />
          </div>
        </div>

        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <Label className="text-muted-foreground">Language</Label>
            <Select value={language} onValueChange={setLanguage}>
              <SelectTrigger className="mt-2 bg-muted/30 border-border/70 text-foreground w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-popover border-border/70">
                <SelectItem value="es">Spanish</SelectItem>
                <SelectItem value="en">English</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-muted-foreground">SERP Depth (Top K)</Label>
            <Input
              type="number"
              min={1}
              max={20}
              value={topK}
              onChange={(e) =>
                setTopK(
                  Math.max(
                    1,
                    Math.min(20, Number(e.target.value) || DEFAULT_TOP_K),
                  ),
                )
              }
              className="mt-2 bg-muted/30 border-border/70 text-foreground"
            />
          </div>
        </div>

        <Button
          onClick={analyzeQuery}
          disabled={loading}
          className="glass-button-primary w-full"
        >
          {loading ? (
            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-foreground" />
          ) : (
            <>
              <Search className="w-4 h-4 mr-2" />
              Analyze Query Position (Kimi 2.5 Search)
            </>
          )}
        </Button>
      </div>

      {error && (
        <div className="flex items-center gap-2 text-red-400 py-2">
          <AlertCircle className="w-5 h-5" />
          <span>{error}</span>
        </div>
      )}

      {loadingLatest && !result && (
        <div className="text-center py-10 text-muted-foreground">
          Loading latest query analysis...
        </div>
      )}

      {result && (
        <div className="space-y-6">
          <div className="grid md:grid-cols-2 xl:grid-cols-5 gap-4">
            <div className="bg-muted/30 border border-border rounded-xl p-4">
              <p className="text-sm text-muted-foreground mb-1">Query</p>
              <p className="text-lg font-semibold text-foreground">
                {result.query || "-"}
              </p>
            </div>
            <div className="bg-muted/30 border border-border rounded-xl p-4">
              <p className="text-sm text-muted-foreground mb-1">Market</p>
              <p className="text-2xl font-bold text-foreground">
                {result.market || "-"}
              </p>
            </div>
            <div className="bg-muted/30 border border-border rounded-xl p-4">
              <p className="text-sm text-muted-foreground mb-1">
                Audited Domain
              </p>
              <p className="text-lg font-semibold text-foreground break-all">
                {result.audited_domain || "-"}
              </p>
            </div>
            <div className="bg-muted/30 border border-border rounded-xl p-4">
              <p className="text-sm text-muted-foreground mb-1">Position</p>
              <p className="text-2xl font-bold text-foreground">
                {rankMessage}
              </p>
            </div>
            <div className="bg-muted/30 border border-border rounded-xl p-4">
              <p className="text-sm text-muted-foreground mb-1">
                Product footprint
              </p>
              <p className="text-2xl font-bold text-foreground">
                {result.product_intelligence?.product_pages_count ?? "n/a"}
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                Platform: {platformLabel || "unknown"}
              </p>
            </div>
          </div>

          {result.top_result && (
            <div className="bg-muted/30 border border-border rounded-xl p-6">
              <h3 className="font-semibold text-foreground text-xl mb-3 flex items-center gap-2">
                <Trophy className="w-5 h-5 text-amber-400" />
                Top Result (#1)
              </h3>
              <a
                href={result.top_result.url}
                target="_blank"
                rel="noreferrer"
                className="text-blue-400 hover:text-blue-300 inline-flex items-center gap-2 break-all"
              >
                {result.top_result.title}
                <ExternalLink className="w-4 h-4" />
              </a>
              <p className="text-sm text-muted-foreground mt-2">
                {result.top_result.snippet}
              </p>
            </div>
          )}

          <div className="grid xl:grid-cols-[1.1fr_1fr] gap-6">
            <div className="bg-muted/30 border border-border rounded-xl p-6">
              <h3 className="font-semibold text-foreground text-xl mb-3 flex items-center gap-2">
                <Blocks className="w-5 h-5 text-sky-500" />
                Root Domain Snapshot
              </h3>
              {result.site_root_summary ? (
                <div className="grid sm:grid-cols-2 gap-4">
                  <div className="border border-border rounded-lg p-4 bg-muted/40">
                    <p className="text-xs uppercase tracking-wide text-muted-foreground">
                      Root path
                    </p>
                    <p className="text-base font-semibold text-foreground mt-1">
                      {result.site_root_summary.path || "/"}
                    </p>
                    <p className="text-xs text-muted-foreground mt-2">
                      Overall score:{" "}
                      {result.site_root_summary.overall_score ?? "n/a"}
                    </p>
                  </div>
                  <div className="border border-border rounded-lg p-4 bg-muted/40">
                    <p className="text-xs uppercase tracking-wide text-muted-foreground">
                      Structure signals
                    </p>
                    <p className="text-sm text-foreground mt-1">
                      Schema: {result.site_root_summary.schema_score ?? "n/a"} ·
                      Content: {result.site_root_summary.content_score ?? "n/a"}{" "}
                      · H1: {result.site_root_summary.h1_score ?? "n/a"}
                    </p>
                    <p className="text-xs text-muted-foreground mt-2">
                      Critical issues:{" "}
                      {result.site_root_summary.critical_issues ?? "n/a"} ·
                      High: {result.site_root_summary.high_issues ?? "n/a"}
                    </p>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  Root-level audited signals are not available for this run.
                </p>
              )}
            </div>

            <div className="bg-muted/30 border border-border rounded-xl p-6">
              <h3 className="font-semibold text-foreground text-xl mb-3 flex items-center gap-2">
                <Bot className="w-5 h-5 text-violet-500" />
                Ecommerce Intelligence
              </h3>
              <div className="grid gap-3">
                <div className="border border-border rounded-lg p-4 bg-muted/40">
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">
                    Ecommerce detected
                  </p>
                  <p className="text-base font-semibold text-foreground mt-1">
                    {result.product_intelligence == null
                      ? "Unknown"
                      : result.product_intelligence.is_ecommerce
                        ? "Yes"
                        : "No"}
                  </p>
                </div>
                <div className="border border-border rounded-lg p-4 bg-muted/40">
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">
                    Schema completeness
                  </p>
                  <p className="text-base font-semibold text-foreground mt-1">
                    {result.product_intelligence?.schema_analysis
                      ?.average_completeness ?? "n/a"}
                  </p>
                  <p className="text-xs text-muted-foreground mt-2">
                    Confidence:{" "}
                    {result.product_intelligence?.confidence_score ?? "n/a"}
                  </p>
                </div>
              </div>
            </div>
          </div>

          <div className="bg-muted/30 border border-border rounded-xl p-6">
            <h3 className="font-semibold text-foreground text-xl mb-3 flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-brand" />
              Root Cause Summary
            </h3>
            {result.root_cause_summary.length > 0 ? (
              <div className="grid lg:grid-cols-2 gap-3">
                {result.root_cause_summary.map((item, idx) => (
                  <div
                    key={`root-cause-${idx}`}
                    className="border border-border rounded-lg p-4 bg-muted/40"
                  >
                    <p className="text-sm font-semibold text-foreground">
                      {item.title}
                    </p>
                    <p className="text-sm text-muted-foreground mt-2">
                      {item.finding}
                    </p>
                    <p className="text-xs text-muted-foreground mt-3">
                      Owner: {item.owner}
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                No root-cause summary available yet.
              </p>
            )}
          </div>

          <div className="bg-muted/30 border border-border rounded-xl p-6">
            <h3 className="font-semibold text-foreground text-xl mb-3 flex items-center gap-2">
              <Target className="w-5 h-5 text-brand" />
              Why You Are Not #1
            </h3>
            {result.why_not_first.length > 0 ? (
              <ul className="space-y-2">
                {result.why_not_first.map((item, idx) => (
                  <li
                    key={`why-${idx}`}
                    className="text-muted-foreground text-sm"
                  >
                    • {item}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground">
                No diagnostics generated yet.
              </p>
            )}
          </div>

          <div className="bg-muted/30 border border-border rounded-xl p-6">
            <h3 className="font-semibold text-foreground text-xl mb-3">
              Disadvantages vs #1
            </h3>
            {result.disadvantages_vs_top1.length > 0 ? (
              <div className="space-y-3">
                {result.disadvantages_vs_top1.map((gap, idx) => (
                  <div
                    key={`gap-${idx}`}
                    className="border border-border rounded-lg p-4 bg-muted/40"
                  >
                    <p className="text-sm font-semibold text-foreground">
                      {gap.area}
                    </p>
                    <p className="text-sm text-muted-foreground mt-1">
                      {gap.gap}
                    </p>
                    {gap.impact ? (
                      <p className="text-xs text-muted-foreground mt-2">
                        Impact: {gap.impact}
                      </p>
                    ) : null}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                No gap details available.
              </p>
            )}
          </div>

          <div className="grid xl:grid-cols-3 gap-6">
            <ActionBlock
              title="Search Engine Fixes"
              icon={<Sparkles className="w-5 h-5 text-emerald-400" />}
              items={result.search_engine_fixes}
              emptyMessage="No search engine fixes generated yet."
            />
            <ActionBlock
              title="Merchandising Fixes"
              icon={<ShoppingBag className="w-5 h-5 text-amber-500" />}
              items={result.merchandising_fixes}
              emptyMessage="No merchandising recommendations were generated for this domain snapshot."
            />
            <div className="bg-muted/30 border border-border rounded-xl p-6">
              <h3 className="font-semibold text-foreground text-xl mb-3 flex items-center gap-2">
                <Zap className="w-5 h-5 text-orange-500" />
                Technical Watchouts
              </h3>
              {result.technical_watchouts.length > 0 ? (
                <div className="space-y-3">
                  {result.technical_watchouts.map((step, idx) => (
                    <div
                      key={`tech-${idx}`}
                      className="border border-border rounded-lg p-4 bg-muted/40"
                    >
                      <div className="flex items-center gap-2">
                        <span className="px-2 py-1 rounded-md text-xs border border-brand/30 bg-brand/10 text-foreground">
                          {step.priority}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          Owner: {step.owner}
                        </span>
                      </div>
                      <p className="text-sm text-foreground mt-2">
                        {step.action}
                      </p>
                      {step.evidence ? (
                        <p className="text-xs text-muted-foreground mt-2">
                          Evidence: {step.evidence}
                        </p>
                      ) : null}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  No technical watchouts generated yet.
                </p>
              )}
            </div>
          </div>

          <ActionBlock
            title="Query-Level Action Plan"
            icon={<Sparkles className="w-5 h-5 text-emerald-400" />}
            items={result.action_plan}
            emptyMessage="No action plan generated yet."
          />

          <div className="bg-muted/30 border border-border rounded-xl p-6">
            <h3 className="font-semibold text-foreground text-xl mb-3">
              SERP Snapshot
            </h3>
            {result.results.length > 0 ? (
              <div className="space-y-3">
                {result.results.map((item) => (
                  <div
                    key={`${item.url}-${item.position}`}
                    className="border border-border rounded-lg p-4 bg-muted/40"
                  >
                    <p className="text-xs text-muted-foreground mb-1">
                      #{item.position} · {item.domain}
                    </p>
                    <a
                      href={item.url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-sm font-semibold text-blue-400 hover:text-blue-300 inline-flex items-center gap-2 break-all"
                    >
                      {item.title}
                      <ExternalLink className="w-3 h-3" />
                    </a>
                    {item.snippet ? (
                      <p className="text-sm text-muted-foreground mt-1">
                        {item.snippet}
                      </p>
                    ) : null}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                No SERP results available.
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
