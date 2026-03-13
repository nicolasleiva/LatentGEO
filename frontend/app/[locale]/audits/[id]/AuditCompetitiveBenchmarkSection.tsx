"use client";

import { Button } from "@/components/ui/button";

type AuditCompetitiveBenchmarkSectionProps = {
  audit: any;
  competitors: any[];
  comparisonSites: Array<{
    name: string;
    score: number;
    color: string;
  }>;
  visibleCompetitors: any[];
  showFullBenchmark: boolean;
  onToggleFullBenchmark: () => void;
  initialCompetitorCount: number;
  expectedCompetitorCount?: number;
};

function resolveDomain(competitor: any) {
  if (competitor?.domain) {
    return competitor.domain;
  }

  try {
    return new URL(competitor?.url || "").hostname.replace(/^www\./, "");
  } catch {
    return competitor?.url || "Competitor";
  }
}

function formatGeoScore(value?: number | null) {
  return typeof value === "number" ? `${value.toFixed(1)}%` : "N/A";
}

function formatSchemaStatus(value?: boolean | null) {
  if (value === true) return "Present";
  if (value === false) return "Missing";
  return "N/A";
}

function formatPercent(value?: number | null) {
  return typeof value === "number" ? `${value.toFixed(0)}%` : "N/A";
}

function formatPassFail(value?: boolean | null) {
  if (value === true) return "Pass";
  if (value === false) return "Fail";
  return "N/A";
}

function formatPassFailFromScore(value?: number | null) {
  if (typeof value !== "number") return "N/A";
  return value > 0 ? "Pass" : "Fail";
}

function formatTone(value?: number | null) {
  return typeof value === "number" ? `${value.toFixed(1)}/10` : "N/A";
}

export default function AuditCompetitiveBenchmarkSection({
  audit,
  competitors,
  comparisonSites,
  visibleCompetitors,
  showFullBenchmark,
  onToggleFullBenchmark,
  initialCompetitorCount,
  expectedCompetitorCount = 0,
}: AuditCompetitiveBenchmarkSectionProps) {
  const isHydratingCompetitors =
    competitors.length === 0 && expectedCompetitorCount > 0;

  return (
    <div
      className="mb-8 rounded-3xl border border-border/70 bg-card p-8 shadow-sm"
      style={{ contentVisibility: "auto", containIntrinsicSize: "1px 980px" }}
    >
      <div className="mb-6 flex flex-col justify-between gap-4 md:flex-row md:items-center">
        <div>
          <h2 className="text-2xl font-bold text-foreground">
            Competitive Benchmark
          </h2>
          <p className="text-sm text-muted-foreground">
            Compare your AI visibility posture against peer domains.
          </p>
        </div>
        <span className="rounded-full border border-border px-3 py-1 text-xs uppercase tracking-wide text-muted-foreground">
          {(competitors.length || expectedCompetitorCount).toString()}{" "}
          competitors
        </span>
      </div>

      {isHydratingCompetitors ? (
        <div className="space-y-2 rounded-2xl border border-dashed border-border bg-muted/30 p-6 text-sm text-muted-foreground">
          <div>Loading {expectedCompetitorCount} audited competitors...</div>
          <div>
            The full competitive benchmark is being hydrated from the audit
            payload.
          </div>
        </div>
      ) : competitors.length === 0 ? (
        <div className="space-y-2 rounded-2xl border border-dashed border-border bg-muted/30 p-6 text-sm text-muted-foreground">
          <div>No competitors identified yet.</div>
          <div>
            Competitor candidates will appear once discovery queries return
            reliable matches.
          </div>
          <div className="text-xs">
            Category: {audit?.category || "Unclassified"}
          </div>
        </div>
      ) : (
        <>
          <div className="mb-8">
            <h3 className="mb-4 text-lg font-semibold text-foreground/80">
              Score Comparison
            </h3>
            <div className="space-y-3">
              {comparisonSites.map((site) => (
                <div key={site.name} className="flex items-center gap-4">
                  <div className="w-40 truncate text-sm text-muted-foreground">
                    {site.name}
                  </div>
                  <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted/40">
                    <div
                      className="h-2 rounded-full"
                      style={{
                        width: `${Math.min(site.score, 100)}%`,
                        backgroundColor: site.color,
                      }}
                    />
                  </div>
                  <div className="w-14 text-right text-sm font-semibold text-foreground">
                    {site.score.toFixed(1)}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <h3 className="text-lg font-semibold text-foreground/80">
              Detailed Benchmark Table
            </h3>
            {competitors.length > initialCompetitorCount && (
              <Button variant="outline" onClick={onToggleFullBenchmark}>
                {showFullBenchmark
                  ? "Show Top Competitors"
                  : `Load All ${competitors.length} Competitors`}
              </Button>
            )}
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-border text-muted-foreground">
                  <th className="p-4 font-medium">Website</th>
                  <th className="p-4 text-center font-medium">GEO Score (%)</th>
                  <th className="p-4 text-center font-medium">Schema</th>
                  <th className="p-4 text-center font-medium">Semantic HTML</th>
                  <th className="p-4 text-center font-medium">E-E-A-T</th>
                  <th className="p-4 text-center font-medium">H1</th>
                  <th className="p-4 text-center font-medium">Tone</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                <tr className="bg-muted/30">
                  <td className="p-4 font-semibold text-foreground">
                    <div className="flex items-center gap-2">
                      <span className="h-2 w-2 rounded-full bg-brand" />
                      Your Site
                    </div>
                  </td>
                  <td className="p-4 text-center font-bold text-brand">
                    {formatGeoScore(
                      audit.geo_score ?? comparisonSites[0]?.score ?? null,
                    )}
                  </td>
                  <td className="p-4 text-center text-foreground/70">
                    {formatSchemaStatus(
                      audit.target_audit?.schema?.schema_presence?.status !=
                        null
                        ? audit.target_audit?.schema?.schema_presence
                            ?.status === "present"
                        : null,
                    )}
                  </td>
                  <td className="p-4 text-center text-foreground/70">
                    {formatPercent(
                      audit.target_audit?.structure?.semantic_html
                        ?.score_percent,
                    )}
                  </td>
                  <td className="p-4 text-center text-foreground/70">
                    {formatPassFail(
                      audit.target_audit?.eeat?.author_presence?.status != null
                        ? audit.target_audit?.eeat?.author_presence?.status ===
                            "pass"
                        : null,
                    )}
                  </td>
                  <td className="p-4 text-center text-foreground/70">
                    {formatPassFail(
                      audit.target_audit?.structure?.h1_check?.status != null
                        ? audit.target_audit?.structure?.h1_check?.status ===
                            "pass"
                        : null,
                    )}
                  </td>
                  <td className="p-4 text-center text-foreground/70">
                    {formatTone(
                      audit.target_audit?.content?.conversational_tone?.score,
                    )}
                  </td>
                </tr>

                {visibleCompetitors.map((competitor: any) => {
                  return (
                    <tr
                      key={
                        competitor.url ??
                        competitor.domain ??
                        JSON.stringify(competitor)
                      }
                      className="transition-colors hover:bg-muted/20"
                    >
                      <td className="p-4 text-muted-foreground">
                        <div className="flex items-center gap-2">
                          <span className="h-2 w-2 rounded-full bg-slate-400" />
                          <a
                            href={competitor.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="hover:text-foreground hover:underline"
                          >
                            {resolveDomain(competitor)}
                          </a>
                        </div>
                      </td>
                      <td className="p-4 text-center font-bold text-foreground/90">
                        {formatGeoScore(competitor.geo_score)}
                      </td>
                      <td className="p-4 text-center text-muted-foreground">
                        {formatSchemaStatus(competitor.schema_present)}
                      </td>
                      <td className="p-4 text-center text-muted-foreground">
                        {formatPercent(competitor.structure_score)}
                      </td>
                      <td className="p-4 text-center text-muted-foreground">
                        {formatPassFailFromScore(competitor.eeat_score)}
                      </td>
                      <td className="p-4 text-center text-muted-foreground">
                        {formatPassFail(competitor.h1_present)}
                      </td>
                      <td className="p-4 text-center text-muted-foreground">
                        {formatTone(competitor.tone_score)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
