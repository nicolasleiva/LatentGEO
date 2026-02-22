"use client";

import { useState, useEffect } from "react";
import { useParams, usePathname, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Header } from "@/components/header";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { withLocale } from "@/lib/locale-routing";
import {
  Loader2,
  ArrowLeft,
  TrendingUp,
  TrendingDown,
  Award,
  AlertCircle,
} from "lucide-react";

export default function AuditAnalyticsPage() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useParams<{ id: string }>();
  const auditId = parseInt(params?.id || "0");
  const [loading, setLoading] = useState(true);
  const [analytics, setAnalytics] = useState<any>(null);
  const [competitorData, setCompetitorData] = useState<any>(null);
  const [issuesData, setIssuesData] = useState<any>(null);

  useEffect(() => {
    const loadAnalytics = async () => {
      try {
        const [analyticsRes, competitorRes, issuesRes] = await Promise.all([
          api.getAuditAnalytics(auditId),
          api.getCompetitorAnalysis(auditId).catch(() => null),
          api.getIssuesByPriority(auditId).catch(() => null),
        ]);
        setAnalytics(analyticsRes);
        setCompetitorData(competitorRes);
        setIssuesData(issuesRes);
      } catch (error) {
        console.error("Error loading analytics:", error);
      } finally {
        setLoading(false);
      }
    };
    loadAnalytics();
  }, [auditId]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-12 w-12 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!analytics) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6">
        <Card className="glass-card p-12 text-center">
          <AlertCircle className="h-16 w-16 text-red-500 mx-auto mb-4" />
          <h3 className="text-xl font-semibold text-foreground mb-2">
            Analytics Not Available
          </h3>
          <Button
            onClick={() => router.push(withLocale(pathname, `/audits/${auditId}`))}
            className="glass-button-primary"
          >
            Back to Audit
          </Button>
        </Card>
      </div>
    );
  }

  const { scores, issues, pages, domain, is_ymyl, category } = analytics;

  const getScoreColor = (score: number) => {
    if (score >= 8) return "text-emerald-600";
    if (score >= 5) return "text-amber-500";
    return "text-red-500";
  };

  const getScoreBg = (score: number) => {
    if (score >= 8) return "bg-emerald-500/10 border-emerald-500/20";
    if (score >= 5) return "bg-amber-500/10 border-amber-500/20";
    return "bg-red-500/10 border-red-500/20";
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Header />
      <main className="max-w-7xl mx-auto px-6 py-12">
        {/* Header */}
        <div className="mb-8 animate-fade-up">
          <div className="flex items-center gap-4 mb-2">
            <Button
              variant="ghost"
              onClick={() =>
                router.push(withLocale(pathname, `/audits/${auditId}`))
              }
              className="text-muted-foreground hover:text-foreground hover:bg-muted/50"
            >
              <ArrowLeft className="h-4 w-4 mr-2" /> Back to Audit
            </Button>
            <div className="h-6 w-px bg-border" />
            <h1 className="text-3xl md:text-4xl font-semibold tracking-tight">
              Analytics: {domain}
            </h1>
          </div>
          <div className="flex items-center gap-2">
            {is_ymyl && (
              <Badge className="bg-amber-500/10 text-amber-600 border-amber-500/30">
                YMYL
              </Badge>
            )}
            {category && (
              <Badge
                variant="outline"
                className="border-border/70 bg-muted/40 text-muted-foreground"
              >
                {category}
              </Badge>
            )}
          </div>
        </div>

        <div className="space-y-6">
          {/* Score Cards */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 animate-fade-up">
            {Object.entries(scores).map(([key, value]: [string, any]) => (
              <Card
                key={key}
                className={`glass-card p-4 border ${getScoreBg(value)}`}
              >
                <div className="text-xs text-muted-foreground mb-1 uppercase">
                  {key.replace("_score", "").replace("_", " ")}
                </div>
                <div className={`text-2xl font-bold ${getScoreColor(value)}`}>
                  {value.toFixed(1)}
                </div>
                <div className="text-xs text-muted-foreground/70">/ 10.0</div>
              </Card>
            ))}
          </div>

          {/* Issues Summary */}
          <Card className="glass-card p-6 animate-fade-up">
            <h2 className="text-xl font-semibold text-foreground mb-6">
              Issues Summary
            </h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="p-4 bg-red-500/10 rounded-lg border border-red-500/20">
                <div className="text-xs text-red-600 mb-1">CRITICAL</div>
                <div className="text-3xl font-semibold text-red-500">
                  {issues.critical}
                </div>
              </div>
              <div className="p-4 bg-orange-500/10 rounded-lg border border-orange-500/20">
                <div className="text-xs text-orange-600 mb-1">HIGH</div>
                <div className="text-3xl font-semibold text-orange-500">
                  {issues.high}
                </div>
              </div>
              <div className="p-4 bg-yellow-500/10 rounded-lg border border-yellow-500/20">
                <div className="text-xs text-amber-600 mb-1">MEDIUM</div>
                <div className="text-3xl font-semibold text-amber-500">
                  {issues.medium}
                </div>
              </div>
              <div className="p-4 bg-brand/10 rounded-lg border border-brand/20">
                <div className="text-xs text-brand mb-1">LOW</div>
                <div className="text-3xl font-semibold text-brand">
                  {issues.low}
                </div>
              </div>
            </div>
            <div className="mt-4 p-4 glass-panel rounded-lg border border-border">
              <div className="text-sm text-muted-foreground">Total Issues</div>
              <div className="text-2xl font-semibold text-foreground">
                {issues.total}
              </div>
            </div>
          </Card>

          {/* Competitor Analysis */}
          {competitorData && (
            <Card className="glass-card p-6 animate-fade-up">
              <h2 className="text-xl font-semibold text-foreground mb-6">
                Competitor Benchmark
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
                <div className="text-center p-6 glass-panel rounded-xl border border-border">
                  <div className="text-sm text-muted-foreground mb-2">
                    Your GEO Score
                  </div>
                  <div
                    className={`text-4xl font-semibold ${getScoreColor(competitorData.your_geo_score)}`}
                  >
                    {competitorData.your_geo_score.toFixed(1)}%
                  </div>
                </div>
                <div className="text-center p-6 glass-panel rounded-xl border border-border">
                  <div className="text-sm text-muted-foreground mb-2">
                    Competitor Average
                  </div>
                  <div className="text-4xl font-semibold text-foreground">
                    {competitorData.average_competitor_score.toFixed(1)}%
                  </div>
                </div>
                <div className="text-center p-6 glass-panel rounded-xl border border-border">
                  <div className="text-sm text-muted-foreground mb-2">
                    Position
                  </div>
                  <div className="flex items-center justify-center gap-2">
                    {competitorData.your_geo_score >
                    competitorData.average_competitor_score ? (
                      <>
                        <TrendingUp className="h-6 w-6 text-emerald-500" />
                        <span className="text-lg font-semibold text-emerald-600">
                          Above Average
                        </span>
                      </>
                    ) : (
                      <>
                        <TrendingDown className="h-6 w-6 text-red-500" />
                        <span className="text-lg font-semibold text-red-500">
                          Below Average
                        </span>
                      </>
                    )}
                  </div>
                </div>
              </div>

              {/* Competitors List */}
              {competitorData.competitors &&
                competitorData.competitors.length > 0 && (
                  <div className="space-y-2">
                    <h3 className="text-sm font-medium text-muted-foreground mb-3">
                      Top Competitors
                    </h3>
                    {competitorData.competitors
                      .slice(0, 5)
                      .map((comp: any, idx: number) => (
                        <div
                          key={idx}
                          className="flex items-center justify-between p-3 glass-panel rounded-lg border border-border"
                        >
                          <div className="flex items-center gap-3">
                            <div
                              className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${
                                idx === 0
                                  ? "bg-amber-500/10 text-amber-600"
                                  : "bg-muted/60 text-muted-foreground"
                              }`}
                            >
                              {idx + 1}
                            </div>
                            <div>
                              <div className="font-medium text-foreground">
                                {comp.domain}
                              </div>
                              <div className="text-xs text-muted-foreground">
                                {comp.url}
                              </div>
                            </div>
                          </div>
                          <div
                            className={`text-lg font-bold ${getScoreColor(comp.geo_score)}`}
                          >
                            {comp.geo_score.toFixed(1)}%
                          </div>
                        </div>
                      ))}
                  </div>
                )}

              {/* Identified Gaps */}
              {competitorData.identified_gaps &&
                competitorData.identified_gaps.length > 0 && (
                  <div className="mt-6 p-4 bg-amber-500/10 border border-amber-500/20 rounded-lg">
                    <h3 className="text-sm font-medium text-amber-600 mb-3 flex items-center gap-2">
                      <AlertCircle className="h-4 w-4" />
                      Identified Gaps
                    </h3>
                    <ul className="space-y-2">
                      {competitorData.identified_gaps.map(
                        (gap: string, idx: number) => (
                          <li
                            key={idx}
                            className="text-sm text-muted-foreground flex items-start gap-2"
                          >
                            <span className="text-amber-500">•</span>
                            {gap}
                          </li>
                        ),
                      )}
                    </ul>
                  </div>
                )}
            </Card>
          )}

          {/* Pages Performance */}
          <Card className="glass-card p-6 animate-fade-up">
            <h2 className="text-xl font-semibold text-foreground mb-6">
              Pages Performance
            </h2>
            <div className="space-y-2">
              {pages.slice(0, 10).map((page: any, idx: number) => (
                <div
                  key={idx}
                  className="flex items-center justify-between p-4 glass-panel rounded-lg border border-border hover:bg-muted/50 transition-all"
                >
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-foreground truncate">
                      {page.path || "/"}
                    </div>
                    <div className="text-xs text-muted-foreground truncate">
                      {page.url}
                    </div>
                  </div>
                  <div className="flex items-center gap-4 ml-4">
                    <div className="text-center">
                      <div className="text-xs text-muted-foreground">Score</div>
                      <div
                        className={`text-lg font-bold ${getScoreColor(page.overall_score)}`}
                      >
                        {page.overall_score.toFixed(1)}
                      </div>
                    </div>
                    <div className="text-center">
                      <div className="text-xs text-muted-foreground">
                        Issues
                      </div>
                      <div className="text-lg font-bold text-red-500">
                        {page.issues.critical +
                          page.issues.high +
                          page.issues.medium +
                          page.issues.low}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
            {pages.length > 10 && (
              <div className="mt-4 text-center text-sm text-muted-foreground">
                Showing 10 of {pages.length} pages
              </div>
            )}
          </Card>

          {/* Issues by Priority */}
          {issuesData && issuesData.by_priority && (
            <Card className="glass-card p-6 animate-fade-up">
              <h2 className="text-xl font-semibold text-foreground mb-6">
                Issues by Priority ({issuesData.total_issues} total)
              </h2>
              <div className="space-y-6">
                {Object.entries(issuesData.by_priority).map(
                  ([priority, items]: [string, any]) =>
                    items.length > 0 && (
                      <div key={priority}>
                        <h3
                          className={`text-sm font-medium mb-3 ${
                            priority === "CRITICAL"
                              ? "text-red-500"
                              : priority === "HIGH"
                                ? "text-orange-500"
                                : priority === "MEDIUM"
                                  ? "text-amber-500"
                                  : "text-brand"
                          }`}
                        >
                          {priority} ({items.length})
                        </h3>
                        <div className="space-y-2">
                          {items.slice(0, 5).map((issue: any, idx: number) => (
                            <div
                              key={idx}
                              className="p-3 glass-panel rounded-lg border border-border text-sm"
                            >
                              <div className="font-medium text-foreground mb-1">
                                {issue.description}
                              </div>
                              {issue.page_path && (
                                <div className="text-xs text-muted-foreground mb-1">
                                  Page: {issue.page_path}
                                </div>
                              )}
                              {issue.suggestion && (
                                <div className="text-xs text-muted-foreground">
                                  💡 {issue.suggestion}
                                </div>
                              )}
                            </div>
                          ))}
                          {items.length > 5 && (
                            <div className="text-xs text-muted-foreground text-center py-2">
                              + {items.length - 5} more {priority.toLowerCase()}{" "}
                              issues
                            </div>
                          )}
                        </div>
                      </div>
                    ),
                )}
              </div>
            </Card>
          )}
        </div>
      </main>
    </div>
  );
}
