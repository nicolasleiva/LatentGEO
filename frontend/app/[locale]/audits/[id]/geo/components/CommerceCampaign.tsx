'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  ExternalLink,
  Search,
  Sparkles,
  Target,
  Trophy,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { fetchWithBackendAuth } from '@/lib/backend-auth';

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
  evidence: CommerceEvidenceItem[];
  provider?: string;
}

interface CommerceCampaignProps {
  auditId: number;
  backendUrl: string;
}

const DEFAULT_TOP_K = 10;

const toNonEmptyString = (value: unknown, fallback = ''): string => {
  if (typeof value === 'string' && value.trim()) return value.trim();
  return fallback;
};

const toNumberOrNull = (value: unknown): number | null => {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return null;
};

const normalizeResultItem = (item: any, index: number): CommerceResultItem | null => {
  if (!item || typeof item !== 'object') return null;
  const url = toNonEmptyString(item.url);
  const domain = toNonEmptyString(item.domain);
  if (!url || !domain) return null;
  const position = toNumberOrNull(item.position) ?? index + 1;
  return {
    position,
    title: toNonEmptyString(item.title, domain),
    url,
    domain,
    snippet: toNonEmptyString(item.snippet),
  };
};

const normalizeAnalysis = (payload: any): CommerceQueryAnalysis | null => {
  if (!payload || typeof payload !== 'object') return null;

  const results = Array.isArray(payload.results)
    ? payload.results
        .map((item: any, index: number) => normalizeResultItem(item, index))
        .filter((item: CommerceResultItem | null): item is CommerceResultItem => Boolean(item))
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
      ? payload.why_not_first.map((item: any) => toNonEmptyString(item)).filter(Boolean)
      : [],
    disadvantages_vs_top1: Array.isArray(payload.disadvantages_vs_top1)
      ? payload.disadvantages_vs_top1
          .map((item: any) => ({
            area: toNonEmptyString(item?.area, 'Gap'),
            gap: toNonEmptyString(item?.gap),
            impact: toNonEmptyString(item?.impact),
          }))
          .filter((item: CommerceGapItem) => item.gap.length > 0)
      : [],
    action_plan: Array.isArray(payload.action_plan)
      ? payload.action_plan
          .map((item: any) => ({
            priority: toNonEmptyString(item?.priority, 'P2'),
            action: toNonEmptyString(item?.action),
            expected_impact: toNonEmptyString(item?.expected_impact, 'Medium'),
            evidence: toNonEmptyString(item?.evidence),
          }))
          .filter((item: CommerceActionItem) => item.action.length > 0)
      : [],
    evidence: Array.isArray(payload.evidence)
      ? payload.evidence
          .map((item: any) => ({
            title: toNonEmptyString(item?.title, toNonEmptyString(item?.url, 'Source')),
            url: toNonEmptyString(item?.url),
          }))
          .filter((item: CommerceEvidenceItem) => item.url.length > 0)
      : [],
    provider: toNonEmptyString(payload.provider),
  };
};

export default function CommerceCampaign({ auditId, backendUrl }: CommerceCampaignProps) {
  const [query, setQuery] = useState('');
  const [market, setMarket] = useState('AR');
  const [language, setLanguage] = useState('es');
  const [topK, setTopK] = useState(DEFAULT_TOP_K);
  const [result, setResult] = useState<CommerceQueryAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingLatest, setLoadingLatest] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadLatest = async () => {
      setLoadingLatest(true);
      try {
        const res = await fetchWithBackendAuth(`${backendUrl}/api/geo/commerce-query/latest/${auditId}`);
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
        setError(err?.message || 'Failed to load latest analysis');
      } finally {
        setLoadingLatest(false);
      }
    };
    loadLatest();
  }, [auditId, backendUrl]);

  const rankMessage = useMemo(() => {
    if (!result) return '';
    if (result.target_position === null) return `Not ranking in top ${topK}`;
    if (result.target_position === 1) return 'Ranking #1';
    return `Ranking #${result.target_position}`;
  }, [result, topK]);

  const analyzeQuery = async () => {
    const safeQuery = query.trim();
    const safeMarket = market.trim().toUpperCase();
    if (!safeQuery || !safeMarket) {
      setError('Query and market are required.');
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const res = await fetchWithBackendAuth(`${backendUrl}/api/geo/commerce-query/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          audit_id: auditId,
          query: safeQuery,
          market: safeMarket,
          top_k: topK,
          language,
        }),
      });

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
        throw new Error('Invalid analysis payload');
      }

      setResult(normalized);
    } catch (err: any) {
      setError(err?.message || 'Failed to analyze query');
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
              onChange={(e) => setTopK(Math.max(1, Math.min(20, Number(e.target.value) || DEFAULT_TOP_K)))}
              className="mt-2 bg-muted/30 border-border/70 text-foreground"
            />
          </div>
        </div>

        <Button onClick={analyzeQuery} disabled={loading} className="glass-button-primary w-full">
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
        <div className="text-center py-10 text-muted-foreground">Loading latest query analysis...</div>
      )}

      {result && (
        <div className="space-y-6">
          <div className="grid md:grid-cols-4 gap-4">
            <div className="bg-muted/30 border border-border rounded-xl p-4">
              <p className="text-sm text-muted-foreground mb-1">Query</p>
              <p className="text-lg font-semibold text-foreground">{result.query || '-'}</p>
            </div>
            <div className="bg-muted/30 border border-border rounded-xl p-4">
              <p className="text-sm text-muted-foreground mb-1">Market</p>
              <p className="text-2xl font-bold text-foreground">{result.market || '-'}</p>
            </div>
            <div className="bg-muted/30 border border-border rounded-xl p-4">
              <p className="text-sm text-muted-foreground mb-1">Audited Domain</p>
              <p className="text-lg font-semibold text-foreground break-all">{result.audited_domain || '-'}</p>
            </div>
            <div className="bg-muted/30 border border-border rounded-xl p-4">
              <p className="text-sm text-muted-foreground mb-1">Position</p>
              <p className="text-2xl font-bold text-foreground">{rankMessage}</p>
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
              <p className="text-sm text-muted-foreground mt-2">{result.top_result.snippet}</p>
            </div>
          )}

          <div className="bg-muted/30 border border-border rounded-xl p-6">
            <h3 className="font-semibold text-foreground text-xl mb-3 flex items-center gap-2">
              <Target className="w-5 h-5 text-brand" />
              Why You Are Not #1
            </h3>
            {result.why_not_first.length > 0 ? (
              <ul className="space-y-2">
                {result.why_not_first.map((item, idx) => (
                  <li key={`why-${idx}`} className="text-muted-foreground text-sm">
                    • {item}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground">No diagnostics generated yet.</p>
            )}
          </div>

          <div className="bg-muted/30 border border-border rounded-xl p-6">
            <h3 className="font-semibold text-foreground text-xl mb-3">Disadvantages vs #1</h3>
            {result.disadvantages_vs_top1.length > 0 ? (
              <div className="space-y-3">
                {result.disadvantages_vs_top1.map((gap, idx) => (
                  <div key={`gap-${idx}`} className="border border-border rounded-lg p-4 bg-muted/40">
                    <p className="text-sm font-semibold text-foreground">{gap.area}</p>
                    <p className="text-sm text-muted-foreground mt-1">{gap.gap}</p>
                    {gap.impact ? <p className="text-xs text-muted-foreground mt-2">Impact: {gap.impact}</p> : null}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No gap details available.</p>
            )}
          </div>

          <div className="bg-muted/30 border border-border rounded-xl p-6">
            <h3 className="font-semibold text-foreground text-xl mb-3 flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-emerald-400" />
              Action Plan
            </h3>
            {result.action_plan.length > 0 ? (
              <div className="space-y-3">
                {result.action_plan.map((step, idx) => (
                  <div key={`plan-${idx}`} className="border border-border rounded-lg p-4 bg-muted/40">
                    <div className="flex items-center gap-2">
                      <span className="px-2 py-1 rounded-md text-xs border border-brand/30 bg-brand/10 text-foreground">
                        {step.priority}
                      </span>
                      <span className="text-xs text-muted-foreground">Expected impact: {step.expected_impact}</span>
                    </div>
                    <p className="text-sm text-foreground mt-2">{step.action}</p>
                    {step.evidence ? (
                      <p className="text-xs text-muted-foreground mt-2">Evidence: {step.evidence}</p>
                    ) : null}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No action plan generated yet.</p>
            )}
          </div>

          <div className="bg-muted/30 border border-border rounded-xl p-6">
            <h3 className="font-semibold text-foreground text-xl mb-3">SERP Snapshot</h3>
            {result.results.length > 0 ? (
              <div className="space-y-3">
                {result.results.map((item) => (
                  <div key={`${item.url}-${item.position}`} className="border border-border rounded-lg p-4 bg-muted/40">
                    <p className="text-xs text-muted-foreground mb-1">#{item.position} · {item.domain}</p>
                    <a
                      href={item.url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-sm font-semibold text-blue-400 hover:text-blue-300 inline-flex items-center gap-2 break-all"
                    >
                      {item.title}
                      <ExternalLink className="w-3 h-3" />
                    </a>
                    {item.snippet ? <p className="text-sm text-muted-foreground mt-1">{item.snippet}</p> : null}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No SERP results available.</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
