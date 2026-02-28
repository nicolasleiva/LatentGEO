"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AlertCircle, Check, Copy, FileText, Sparkles } from "lucide-react";

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
import { Textarea } from "@/components/ui/textarea";
import { fetchWithBackendAuth } from "@/lib/backend-auth";

interface KeywordStrategy {
  primary_keyword: string;
  secondary_keywords: string[];
  search_intent: string;
  strategy_mode?: string;
}

interface CompetitorGapMap {
  content?: Array<{ gap: string; impact?: string; recommended_fix?: string }>;
  schema?: Array<{ gap: string; impact?: string; recommended_fix?: string }>;
  eeat?: Array<{ gap: string; impact?: string; recommended_fix?: string }>;
  clarity?: Array<{ gap: string; impact?: string; recommended_fix?: string }>;
  faq?: Array<{ gap: string; impact?: string; recommended_fix?: string }>;
  evidence?: Array<{ gap: string; impact?: string; recommended_fix?: string }>;
}

interface EvidenceSummaryItem {
  claim: string;
  source_url: string;
}

interface SourceItem {
  title: string;
  url: string;
}

interface ArticleError {
  code?: string;
  message?: string;
}

interface ArticleItem {
  index: number;
  title: string;
  slug?: string;
  target_keyword: string;
  focus_url: string;
  competitor_to_beat?: string;
  citation_readiness_score: number;
  markdown?: string;
  meta_title?: string;
  meta_description?: string;
  sources?: SourceItem[];
  keyword_strategy?: KeywordStrategy;
  competitor_gap_map?: CompetitorGapMap;
  evidence_summary?: EvidenceSummaryItem[];
  generation_status?: "completed" | "failed" | string;
  generation_error?: ArticleError | null;
}

interface BatchSummary {
  generated_count?: number;
  failed_count?: number;
  average_citation_readiness_score?: number;
  language?: string;
  tone?: string;
  include_schema?: boolean;
}

interface BatchResponse {
  batch_id: number;
  status: string;
  summary: BatchSummary;
  articles: ArticleItem[];
}

interface ArticleEngineProps {
  auditId: number;
  backendUrl: string;
}

const TERMINAL_BATCH_STATUSES = new Set([
  "completed",
  "failed",
  "partial_failed",
]);

const safeText = (value: unknown, fallback = ""): string => {
  if (typeof value === "string" && value.trim()) return value.trim();
  return fallback;
};

const normalizeArticle = (item: any): ArticleItem => ({
  index: Number(item?.index) || 0,
  title: safeText(item?.title, "Untitled article"),
  slug: safeText(item?.slug),
  target_keyword: safeText(item?.target_keyword),
  focus_url: safeText(item?.focus_url),
  competitor_to_beat: safeText(item?.competitor_to_beat),
  citation_readiness_score: Number(item?.citation_readiness_score) || 0,
  markdown: safeText(item?.markdown),
  meta_title: safeText(item?.meta_title),
  meta_description: safeText(item?.meta_description),
  sources: Array.isArray(item?.sources)
    ? item.sources
        .map((src: any) => ({
          title: safeText(src?.title, safeText(src?.url, "Source")),
          url: safeText(src?.url),
        }))
        .filter((src: SourceItem) => Boolean(src.url))
    : [],
  keyword_strategy:
    item?.keyword_strategy && typeof item.keyword_strategy === "object"
      ? {
          primary_keyword: safeText(item.keyword_strategy.primary_keyword),
          secondary_keywords: Array.isArray(
            item.keyword_strategy.secondary_keywords,
          )
            ? item.keyword_strategy.secondary_keywords
                .map((kw: any) => safeText(kw))
                .filter(Boolean)
            : [],
          search_intent: safeText(item.keyword_strategy.search_intent),
          strategy_mode: safeText(item.keyword_strategy.strategy_mode),
        }
      : undefined,
  competitor_gap_map:
    item?.competitor_gap_map && typeof item.competitor_gap_map === "object"
      ? item.competitor_gap_map
      : undefined,
  evidence_summary: Array.isArray(item?.evidence_summary)
    ? item.evidence_summary
        .map((entry: any) => ({
          claim: safeText(entry?.claim),
          source_url: safeText(entry?.source_url),
        }))
        .filter(
          (entry: EvidenceSummaryItem) =>
            Boolean(entry.claim) || Boolean(entry.source_url),
        )
    : [],
  generation_status: safeText(item?.generation_status),
  generation_error:
    item?.generation_error && typeof item.generation_error === "object"
      ? {
          code: safeText(item.generation_error.code),
          message: safeText(item.generation_error.message),
        }
      : null,
});

const normalizeBatch = (payload: any): BatchResponse | null => {
  if (!payload || typeof payload !== "object") return null;
  const batchId = Number(payload.batch_id);
  if (!batchId) return null;
  return {
    batch_id: batchId,
    status: safeText(payload.status, "processing"),
    summary: (payload.summary && typeof payload.summary === "object"
      ? payload.summary
      : {}) as BatchSummary,
    articles: Array.isArray(payload.articles)
      ? payload.articles.map(normalizeArticle)
      : [],
  };
};

const parseErrorMessage = async (res: Response): Promise<string> => {
  const raw = await res.text();
  if (!raw) return `Request failed (${res.status})`;
  try {
    const parsed = JSON.parse(raw);
    const detail = parsed?.detail;
    if (typeof detail === "string") return detail;
    if (detail && typeof detail === "object") {
      const code = safeText(detail.code);
      const message = safeText(detail.message || detail.detail);
      return (
        [code, message].filter(Boolean).join(": ") ||
        `Request failed (${res.status})`
      );
    }
    return safeText(parsed?.message, `Request failed (${res.status})`);
  } catch {
    return raw;
  }
};

export default function ArticleEngine({
  auditId,
  backendUrl,
}: ArticleEngineProps) {
  const [count, setCount] = useState(3);
  const [language, setLanguage] = useState("en");
  const [tone, setTone] = useState("executive");
  const [includeSchema, setIncludeSchema] = useState(true);
  const [loading, setLoading] = useState(false);
  const [loadingLatest, setLoadingLatest] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<BatchResponse | null>(null);
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, []);

  const fetchBatchStatus = useCallback(
    async (batchId: number) => {
      const res = await fetchWithBackendAuth(
        `${backendUrl}/api/v1/geo/article-engine/status/${batchId}`,
      );
      if (res.status === 401) {
        stopPolling();
        // Redirect to unified sign-in if session expired
        window.location.href = "/auth/login";
        return null;
      }
      if (!res.ok) {
        throw new Error(await parseErrorMessage(res));
      }
      const payload = normalizeBatch(await res.json());
      if (!payload) {
        throw new Error("Invalid article batch payload");
      }
      setResult(payload);
      if (TERMINAL_BATCH_STATUSES.has(payload.status)) {
        stopPolling();
      }
      return payload;
    },
    [backendUrl, stopPolling],
  );

  const startPolling = useCallback(
    (batchId: number) => {
      stopPolling();
      pollingRef.current = setInterval(() => {
        fetchBatchStatus(batchId).catch((pollError) => {
          // If pollError is null (from 401 redirect), do nothing
          if (!pollError) return;
          
          setError(
            pollError instanceof Error ? pollError.message : String(pollError),
          );
          stopPolling();
        });
      }, 3000);
    },
    [fetchBatchStatus, stopPolling],
  );

  useEffect(() => {
    const fetchLatest = async () => {
      setLoadingLatest(true);
      try {
        const res = await fetchWithBackendAuth(
          `${backendUrl}/api/v1/geo/article-engine/latest/${auditId}`,
        );
        if (res.status === 401) {
          window.location.href = "/auth/login";
          return;
        }
        if (!res.ok) throw new Error(await parseErrorMessage(res));
        const raw = await res.json();
        if (raw?.has_data) {
          const payload = normalizeBatch(raw);
          if (payload) {
            setResult(payload);
            if (!TERMINAL_BATCH_STATUSES.has(payload.status)) {
              startPolling(payload.batch_id);
            }
          }
        }
      } catch (err: any) {
        setError(err?.message || "Failed to fetch latest article batch");
      } finally {
        setLoadingLatest(false);
      }
    };
    fetchLatest();
    return () => stopPolling();
  }, [auditId, backendUrl, startPolling, stopPolling]);

  const generateArticles = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchWithBackendAuth(
        `${backendUrl}/api/v1/geo/article-engine/generate`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            audit_id: auditId,
            article_count: count,
            language,
            tone,
            include_schema: includeSchema,
            run_async: true,
          }),
        },
      );
      if (res.status === 401) {
        window.location.href = "/auth/login";
        return;
      }
      if (!res.ok) throw new Error(await parseErrorMessage(res));
      const payload = normalizeBatch(await res.json());
      if (!payload) throw new Error("Invalid article batch response");
      setResult(payload);
      if (!TERMINAL_BATCH_STATUSES.has(payload.status)) {
        startPolling(payload.batch_id);
      }
    } catch (err: any) {
      setError(err?.message || "Failed to generate articles");
    } finally {
      setLoading(false);
    }
  };

  const copyArticle = async (article: ArticleItem) => {
    const content = article.markdown?.trim()
      ? article.markdown
      : "# Article not generated yet";
    await navigator.clipboard.writeText(content);
    setCopiedIndex(article.index);
    setTimeout(() => setCopiedIndex(null), 1800);
  };

  const renderGapGroup = (
    label: string,
    items: Array<{
      gap: string;
      impact?: string;
      recommended_fix?: string;
    }> = [],
  ) => {
    if (!items.length) return null;
    return (
      <div className="space-y-1">
        <p className="text-xs uppercase tracking-wide text-muted-foreground">
          {label}
        </p>
        {items.slice(0, 2).map((item, idx) => (
          <p key={`${label}-${idx}`} className="text-sm text-muted-foreground">
            • {item.gap}
          </p>
        ))}
      </div>
    );
  };

  return (
    <div className="space-y-6">
      <div className="bg-muted/30 border border-border rounded-xl p-6 space-y-4">
        <div className="grid md:grid-cols-4 gap-4">
          <div>
            <Label className="text-muted-foreground">Article Count</Label>
            <Input
              type="number"
              min={1}
              max={12}
              value={count}
              onChange={(e) =>
                setCount(Math.max(1, Math.min(12, Number(e.target.value) || 1)))
              }
              className="mt-2 bg-muted/30 border-border/70 text-foreground"
            />
          </div>
          <div>
            <Label className="text-muted-foreground">Language</Label>
            <Select value={language} onValueChange={setLanguage}>
              <SelectTrigger className="mt-2 bg-muted/30 border-border/70 text-foreground">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-popover border-border/70">
                <SelectItem value="en">English</SelectItem>
                <SelectItem value="es">Spanish</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-muted-foreground">Tone</Label>
            <Select value={tone} onValueChange={setTone}>
              <SelectTrigger className="mt-2 bg-muted/30 border-border/70 text-foreground">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-popover border-border/70">
                <SelectItem value="executive">Executive</SelectItem>
                <SelectItem value="growth">Growth</SelectItem>
                <SelectItem value="technical">Technical</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-end">
            <button
              type="button"
              onClick={() => setIncludeSchema((v) => !v)}
              className={`w-full px-4 py-2 rounded-lg border text-sm transition ${
                includeSchema
                  ? "bg-brand/20 border-brand/40 text-foreground"
                  : "bg-muted/30 border-border/70 text-muted-foreground"
              }`}
            >
              Include Schema: {includeSchema ? "Yes" : "No"}
            </button>
          </div>
        </div>

        <Button
          onClick={generateArticles}
          disabled={loading}
          className="glass-button-primary w-full"
        >
          {loading ? (
            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-foreground" />
          ) : (
            <>
              <Sparkles className="w-4 h-4 mr-2" />
              Generate Article Batch
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
          Loading latest generated articles...
        </div>
      )}

      {result && (
        <div className="space-y-4">
          <div className="bg-muted/30 border border-border rounded-xl p-4 grid md:grid-cols-4 gap-4">
            <div>
              <p className="text-sm text-muted-foreground">Generated</p>
              <p className="text-2xl font-bold text-foreground">
                {result.summary.generated_count ?? 0}
              </p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Failed</p>
              <p className="text-2xl font-bold text-foreground">
                {result.summary.failed_count ?? 0}
              </p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">
                Avg Citation Readiness
              </p>
              <p className="text-2xl font-bold text-foreground">
                {Number(
                  result.summary.average_citation_readiness_score || 0,
                ).toFixed(1)}
              </p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Batch Status</p>
              <p className="text-2xl font-bold text-foreground capitalize">
                {result.status}
              </p>
            </div>
          </div>

          {(Array.isArray(result.articles) ? result.articles : []).map(
            (article) => (
              <div
                key={`${article.index}-${article.title}`}
                className="bg-muted/30 border border-border rounded-xl p-6 space-y-4"
              >
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h3 className="text-xl font-semibold text-foreground">
                      {article.title}
                    </h3>
                    <p className="text-sm text-muted-foreground mt-1">
                      Keyword:{" "}
                      <span className="text-foreground">
                        {article.target_keyword || "-"}
                      </span>{" "}
                      · Focus URL: {article.focus_url || "-"}
                    </p>
                    <p className="text-sm text-muted-foreground">
                      Competitor to beat:{" "}
                      <span className="text-foreground">
                        {article.competitor_to_beat || "N/A"}
                      </span>
                    </p>
                    <p className="text-sm text-muted-foreground">
                      Status:{" "}
                      <span className="text-foreground">
                        {article.generation_status || "unknown"}
                      </span>
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm text-muted-foreground">
                      Citation Score
                    </p>
                    <p className="text-2xl font-bold text-foreground">
                      {article.citation_readiness_score || 0}
                    </p>
                  </div>
                </div>

                {article.keyword_strategy ? (
                  <div className="bg-muted/40 border border-border rounded-lg p-4 space-y-2">
                    <p className="text-sm font-medium text-foreground">
                      Keyword Strategy
                    </p>
                    <p className="text-sm text-muted-foreground">
                      Primary:{" "}
                      <span className="text-foreground">
                        {article.keyword_strategy.primary_keyword || "-"}
                      </span>
                    </p>
                    <p className="text-sm text-muted-foreground">
                      Intent:{" "}
                      <span className="text-foreground">
                        {article.keyword_strategy.search_intent || "-"}
                      </span>
                    </p>
                    {!!article.keyword_strategy.secondary_keywords?.length && (
                      <p className="text-sm text-muted-foreground">
                        Secondary:{" "}
                        <span className="text-foreground">
                          {article.keyword_strategy.secondary_keywords.join(
                            ", ",
                          )}
                        </span>
                      </p>
                    )}
                  </div>
                ) : null}

                {article.competitor_gap_map ? (
                  <div className="bg-muted/40 border border-border rounded-lg p-4 space-y-3">
                    <p className="text-sm font-medium text-foreground">
                      Competitor Gaps
                    </p>
                    {renderGapGroup(
                      "Content",
                      article.competitor_gap_map.content,
                    )}
                    {renderGapGroup(
                      "Schema",
                      article.competitor_gap_map.schema,
                    )}
                    {renderGapGroup("E-E-A-T", article.competitor_gap_map.eeat)}
                    {renderGapGroup(
                      "Clarity",
                      article.competitor_gap_map.clarity,
                    )}
                    {renderGapGroup("FAQ", article.competitor_gap_map.faq)}
                    {renderGapGroup(
                      "Evidence",
                      article.competitor_gap_map.evidence,
                    )}
                  </div>
                ) : null}

                {article.generation_error ? (
                  <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 text-sm text-red-300">
                    <strong>
                      {article.generation_error.code || "Generation error"}:
                    </strong>{" "}
                    {article.generation_error.message || "Unknown failure"}
                  </div>
                ) : null}

                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    onClick={() => copyArticle(article)}
                    className="border-border/70 text-foreground"
                  >
                    {copiedIndex === article.index ? (
                      <>
                        <Check className="w-4 h-4 mr-2" />
                        Copied
                      </>
                    ) : (
                      <>
                        <Copy className="w-4 h-4 mr-2" />
                        Copy Markdown
                      </>
                    )}
                  </Button>
                </div>

                <Textarea
                  value={article.markdown || ""}
                  readOnly
                  className="bg-muted/50 border-border text-foreground min-h-[240px]"
                />

                {!!article.evidence_summary?.length && (
                  <div>
                    <p className="text-sm text-muted-foreground mb-1">
                      Evidence Summary
                    </p>
                    <div className="space-y-1">
                      {article.evidence_summary
                        .slice(0, 5)
                        .map((evidence, idx) => (
                          <p
                            key={`ev-${idx}`}
                            className="text-sm text-muted-foreground"
                          >
                            • {evidence.claim}{" "}
                            {evidence.source_url
                              ? `(${evidence.source_url})`
                              : ""}
                          </p>
                        ))}
                    </div>
                  </div>
                )}

                {!!article.sources?.length && (
                  <div>
                    <p className="text-sm text-muted-foreground mb-1">
                      Sources
                    </p>
                    <div className="space-y-1">
                      {article.sources.map((source, idx) => (
                        <a
                          key={`${source.url}-${idx}`}
                          href={source.url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-sm text-blue-400 hover:text-blue-300 block"
                        >
                          <FileText className="inline w-3 h-3 mr-1" />
                          {source.title}
                        </a>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ),
          )}
        </div>
      )}
    </div>
  );
}

