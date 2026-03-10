"use client";

import { useEffect, useMemo, useState } from "react";
import { BarChart3, TrendingUp, Users } from "lucide-react";

import { fetchWithBackendAuth } from "@/lib/backend-auth";

type BenchmarkSummary = {
  audit_id: number;
  total_competitors: number;
  your_geo_score: number;
  average_competitor_score: number;
  position: string;
  competitors: Array<{
    domain: string;
    url: string;
    geo_score: number;
  }>;
  identified_gaps: string[];
};

type AuditedCompetitor = {
  url: string;
  domain: string;
  geo_score: number;
  schema_present?: boolean;
  structure_score?: number;
  eeat_score?: number;
  h1_present?: boolean;
  tone_score?: number;
};

type AuditedCompetitorBenchmarkProps = {
  auditId: number;
  backendUrl: string;
  active: boolean;
};

const formatScore = (value?: number | null) =>
  Number.isFinite(value) ? Math.round(Number(value)) : 0;

export default function AuditedCompetitorBenchmark({
  auditId,
  backendUrl,
  active,
}: AuditedCompetitorBenchmarkProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<BenchmarkSummary | null>(null);
  const [competitors, setCompetitors] = useState<AuditedCompetitor[]>([]);
  const [hasFetched, setHasFetched] = useState(false);

  useEffect(() => {
    if (!active || hasFetched) return;

    let ignore = false;

    const run = async () => {
      setLoading(true);
      setError(null);
      try {
        const [summaryRes, competitorsRes] = await Promise.all([
          fetchWithBackendAuth(
            `${backendUrl}/api/v1/analytics/competitors/${auditId}`,
          ),
          fetchWithBackendAuth(
            `${backendUrl}/api/v1/audits/${auditId}/competitors?limit=10`,
          ),
        ]);

        if (!summaryRes.ok || !competitorsRes.ok) {
          throw new Error("Failed to load competitor benchmark");
        }

        const [summaryPayload, competitorsPayload] = await Promise.all([
          summaryRes.json(),
          competitorsRes.json(),
        ]);

        if (ignore) return;

        setSummary(summaryPayload);
        setCompetitors(
          Array.isArray(competitorsPayload) ? competitorsPayload : [],
        );
        setHasFetched(true);
      } catch (err: any) {
        if (ignore) return;
        setError(err?.message || "Failed to load competitor benchmark");
      } finally {
        if (!ignore) {
          setLoading(false);
        }
      }
    };

    void run();

    return () => {
      ignore = true;
    };
  }, [active, auditId, backendUrl, hasFetched]);

  const chartRows = useMemo(() => {
    const rows = [
      {
        label: "Your site",
        score: summary?.your_geo_score ?? 0,
        tone: "bg-brand",
      },
      ...((summary?.competitors || []).map((competitor) => ({
        label: competitor.domain,
        score: competitor.geo_score || 0,
        tone: "bg-emerald-500",
      })) || []),
    ];
    return rows.slice(0, 6);
  }, [summary?.competitors, summary?.your_geo_score]);

  if (!active) {
    return null;
  }

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="grid gap-4 md:grid-cols-3">
          {[1, 2, 3].map((index) => (
            <div
              key={`benchmark-skeleton-${index}`}
              className="h-28 animate-pulse rounded-2xl border border-border bg-muted/40"
            />
          ))}
        </div>
        <div className="h-64 animate-pulse rounded-2xl border border-border bg-muted/40" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-2xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-700">
        {error}
      </div>
    );
  }

  const hasCompetitorData =
    (summary?.total_competitors || 0) > 0 || competitors.length > 0;

  if (!hasCompetitorData) {
    return (
      <div className="rounded-2xl border border-dashed border-border bg-muted/20 p-8 text-center">
        <h3 className="text-lg font-semibold text-foreground">
          No audited competitors available yet
        </h3>
        <p className="mt-2 text-sm text-muted-foreground">
          This benchmark fills automatically once competitor discovery has data
          for the audit. The ad hoc benchmark remains available below for manual
          comparisons.
        </p>
      </div>
    );
  }

  const scoreGap =
    (summary?.your_geo_score || 0) - (summary?.average_competitor_score || 0);

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-2xl border border-border bg-muted/20 p-5">
          <div className="mb-3 flex items-center gap-2 text-xs uppercase tracking-wide text-muted-foreground">
            <TrendingUp className="h-4 w-4" />
            Your GEO Score
          </div>
          <div className="text-3xl font-semibold text-foreground">
            {formatScore(summary?.your_geo_score)}
          </div>
        </div>
        <div className="rounded-2xl border border-border bg-muted/20 p-5">
          <div className="mb-3 flex items-center gap-2 text-xs uppercase tracking-wide text-muted-foreground">
            <Users className="h-4 w-4" />
            Competitor Average
          </div>
          <div className="text-3xl font-semibold text-foreground">
            {formatScore(summary?.average_competitor_score)}
          </div>
        </div>
        <div className="rounded-2xl border border-border bg-muted/20 p-5">
          <div className="mb-3 flex items-center gap-2 text-xs uppercase tracking-wide text-muted-foreground">
            <BarChart3 className="h-4 w-4" />
            Relative Position
          </div>
          <div
            className={`text-3xl font-semibold ${
              scoreGap >= 0 ? "text-emerald-600" : "text-amber-600"
            }`}
          >
            {scoreGap >= 0 ? "+" : ""}
            {formatScore(scoreGap)}
          </div>
          <p className="mt-2 text-sm text-muted-foreground">
            {summary?.position || "Benchmark pending"}
          </p>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <div className="rounded-2xl border border-border bg-muted/20 p-6">
          <h3 className="mb-5 text-lg font-semibold text-foreground">
            Audited Competitor Ranking
          </h3>
          <div className="space-y-4">
            {chartRows.map((row) => (
              <div key={`${row.label}-${row.score}`} className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium text-foreground">{row.label}</span>
                  <span className="text-muted-foreground">
                    {formatScore(row.score)}
                  </span>
                </div>
                <div className="h-2 rounded-full bg-muted">
                  <div
                    className={`h-full rounded-full ${row.tone}`}
                    style={{ width: `${Math.max(4, Math.min(100, row.score))}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-2xl border border-border bg-muted/20 p-6">
          <h3 className="mb-5 text-lg font-semibold text-foreground">
            Identified Gaps
          </h3>
          {(summary?.identified_gaps || []).length > 0 ? (
            <div className="space-y-3">
              {summary?.identified_gaps.map((gap) => (
                <div
                  key={gap}
                  className="rounded-xl border border-border bg-card px-4 py-3 text-sm text-foreground"
                >
                  {gap}
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              No structured gap list is available yet, but the audited
              competitor table below still reflects comparative scores and
              signal coverage.
            </p>
          )}
        </div>
      </div>

      <div className="rounded-2xl border border-border bg-card p-6">
        <h3 className="mb-5 text-lg font-semibold text-foreground">
          Audited Competitor Signals
        </h3>
        <div className="overflow-x-auto">
          <table className="min-w-full border-separate border-spacing-y-3">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                <th className="pr-4">Domain</th>
                <th className="pr-4">GEO</th>
                <th className="pr-4">Schema</th>
                <th className="pr-4">Structure</th>
                <th className="pr-4">E-E-A-T</th>
                <th className="pr-4">H1</th>
                <th>Tone</th>
              </tr>
            </thead>
            <tbody>
              {competitors.map((competitor) => (
                <tr
                  key={`${competitor.domain}-${competitor.url}`}
                  className="rounded-2xl bg-muted/20 text-sm text-foreground"
                >
                  <td className="rounded-l-2xl px-4 py-3 font-medium">
                    {competitor.domain}
                  </td>
                  <td className="px-4 py-3">{formatScore(competitor.geo_score)}</td>
                  <td className="px-4 py-3">
                    {competitor.schema_present ? "Present" : "Missing"}
                  </td>
                  <td className="px-4 py-3">
                    {formatScore(competitor.structure_score)}
                  </td>
                  <td className="px-4 py-3">
                    {formatScore(competitor.eeat_score)}
                  </td>
                  <td className="px-4 py-3">
                    {competitor.h1_present ? "Pass" : "Gap"}
                  </td>
                  <td className="rounded-r-2xl px-4 py-3">
                    {Number(competitor.tone_score || 0).toFixed(1)}/10
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
