"use client";

import { useState, useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Header } from "@/components/header";
import { ScoreHistoryChart } from "@/components/score-history-chart";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { withLocale } from "@/lib/locale-routing";
import {
  Loader2,
  TrendingUp,
  Users,
  AlertTriangle,
  CheckCircle,
  BarChart3,
  Target,
  History,
  ChevronDown,
} from "lucide-react";

export default function AnalyticsPage() {
  const router = useRouter();
  const pathname = usePathname();
  const [loading, setLoading] = useState(true);
  const [dashboardData, setDashboardData] = useState<any>(null);
  const [selectedDomain, setSelectedDomain] = useState<string>("");
  const [showHistory, setShowHistory] = useState(false);

  useEffect(() => {
    loadDashboard();
  }, []);

  const loadDashboard = async () => {
    try {
      const data = await api.getDashboardData();
      setDashboardData(data);
    } catch (error) {
      console.error("Error loading dashboard:", error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-12 w-12 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!dashboardData) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6">
        <Card className="glass-card p-12 text-center max-w-md">
          <AlertTriangle className="h-16 w-16 text-amber-500 mx-auto mb-4" />
          <h3 className="text-xl font-semibold text-foreground mb-2">
            No Data Available
          </h3>
          <p className="text-muted-foreground mb-6">
            Unable to load analytics data
          </p>
          <Button onClick={loadDashboard} className="glass-button-primary">
            Retry
          </Button>
        </Card>
      </div>
    );
  }

  const { summary, recent_audits, metrics } = dashboardData;

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Header />

      <main className="max-w-7xl mx-auto px-6 py-12">
        <div className="mb-8 animate-fade-up">
          <h1 className="text-3xl md:text-4xl font-semibold tracking-tight">
            Visibility Command Center
          </h1>
          <p className="text-muted-foreground mt-2 max-w-2xl">
            Monitor execution health, queue throughput, and competitive AI visibility trends.
          </p>
        </div>

        <div className="max-w-7xl mx-auto space-y-6">
          {/* Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 animate-fade-up">
            <Card className="glass-card p-6">
              <div className="flex items-center justify-between mb-2">
                <BarChart3 className="h-5 w-5 text-brand" />
                <Badge
                  variant="outline"
                  className="bg-brand/10 text-brand border-brand/30"
                >
                  Total
                </Badge>
              </div>
              <div className="text-3xl font-semibold text-foreground mb-1">
                {summary.total_audits}
              </div>
              <div className="text-sm text-muted-foreground">Audits in system</div>
            </Card>

            <Card className="glass-card p-6">
              <div className="flex items-center justify-between mb-2">
                <CheckCircle className="h-5 w-5 text-emerald-500" />
                <Badge
                  variant="outline"
                  className="bg-emerald-500/10 text-emerald-600 border-emerald-500/30"
                >
                  {summary.success_rate.toFixed(0)}%
                </Badge>
              </div>
              <div className="text-3xl font-semibold text-foreground mb-1">
                {summary.completed_audits}
              </div>
              <div className="text-sm text-muted-foreground">Successfully completed</div>
            </Card>

            <Card className="glass-card p-6">
              <div className="flex items-center justify-between mb-2">
                <Loader2 className="h-5 w-5 text-amber-500 animate-soft-pulse" />
                <Badge
                  variant="outline"
                  className="bg-amber-500/10 text-amber-600 border-amber-500/30"
                >
                  Active
                </Badge>
              </div>
              <div className="text-3xl font-semibold text-foreground mb-1">
                {summary.running_audits}
              </div>
              <div className="text-sm text-muted-foreground">Currently processing</div>
            </Card>

            <Card className="glass-card p-6">
              <div className="flex items-center justify-between mb-2">
                <Users className="h-5 w-5 text-foreground" />
                <Badge
                  variant="outline"
                  className="bg-muted/50 text-foreground border-border/70"
                >
                  Unique
                </Badge>
              </div>
              <div className="text-3xl font-semibold text-foreground mb-1">
                {metrics.unique_domains}
              </div>
              <div className="text-sm text-muted-foreground">Tracked domains</div>
            </Card>
          </div>

          {/* Metrics Overview */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 animate-fade-up">
            <Card className="glass-card p-6">
              <div className="flex items-center gap-3 mb-4">
                <div className="p-3 bg-red-500/10 rounded-lg">
                  <AlertTriangle className="h-6 w-6 text-red-500" />
                </div>
                <div>
                  <h3 className="font-semibold text-foreground">
                    Remediation Backlog
                  </h3>
                  <p className="text-xs text-muted-foreground">
                    Issues across active projects
                  </p>
                </div>
              </div>
              <div className="text-4xl font-semibold text-red-500 mb-2">
                {metrics.total_issues}
              </div>
              <div className="text-sm text-muted-foreground">
                Average: {metrics.average_issues_per_audit} issues per audit
              </div>
            </Card>

            <Card className="glass-card p-6">
              <div className="flex items-center gap-3 mb-4">
                <div className="p-3 bg-emerald-500/10 rounded-lg">
                  <Target className="h-6 w-6 text-emerald-500" />
                </div>
                <div>
                  <h3 className="font-semibold text-foreground">
                    Completion Reliability
                  </h3>
                  <p className="text-xs text-muted-foreground">
                    Queue conversion rate
                  </p>
                </div>
              </div>
              <div className="text-4xl font-semibold text-emerald-500 mb-2">
                {summary.success_rate.toFixed(1)}%
              </div>
              <div className="text-sm text-muted-foreground">
                {summary.completed_audits} of {summary.total_audits} completed
              </div>
            </Card>

            <Card className="glass-card p-6">
              <div className="flex items-center gap-3 mb-4">
                <div className="p-3 bg-brand/10 rounded-lg">
                  <TrendingUp className="h-6 w-6 text-brand" />
                </div>
                <div>
                  <h3 className="font-semibold text-foreground">Operational Health</h3>
                  <p className="text-xs text-muted-foreground">
                    Failure pressure indicator
                  </p>
                </div>
              </div>
              <div className="text-4xl font-semibold text-brand mb-2">
                {summary.failed_audits === 0 ? "Excellent" : "Good"}
              </div>
              <div className="text-sm text-muted-foreground">
                {summary.failed_audits} failed runs requiring review
              </div>
            </Card>
          </div>

          {/* Score History Section */}
          <Card className="glass-card p-6 animate-fade-up">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-brand/10 rounded-lg">
                  <History className="h-5 w-5 text-brand" />
                </div>
                <div>
                  <h2 className="text-xl font-semibold text-foreground">
                    Historical Score Tracking
                  </h2>
                  <p className="text-sm text-muted-foreground">
                    Compare domain-level performance over time
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-4">
                <select
                  value={selectedDomain}
                  onChange={(e) => setSelectedDomain(e.target.value)}
                  className="glass-input rounded-lg px-4 py-2 text-sm"
                >
                  <option value="">Select domain</option>
                  {recent_audits.map((audit: any) => (
                    <option key={audit.domain} value={audit.domain}>
                      {audit.domain}
                    </option>
                  ))}
                </select>

                <Button
                  variant="outline"
                  onClick={() => setShowHistory(!showHistory)}
                  className="gap-2"
                >
                  {showHistory ? "Hide chart" : "Show chart"}
                  <ChevronDown
                    className={`h-4 w-4 transition-transform ${showHistory ? "rotate-180" : ""}`}
                  />
                </Button>
              </div>
            </div>

            {showHistory && selectedDomain ? (
              <ScoreHistoryChart domain={selectedDomain} />
            ) : showHistory && !selectedDomain ? (
              <div className="text-center py-12 text-muted-foreground border border-dashed border-border/60 rounded-2xl glass-panel">
                <History className="h-12 w-12 mx-auto mb-3 opacity-40" />
                <p>Select a domain to view its score history.</p>
              </div>
            ) : null}
          </Card>

          {/* Recent Audits */}
          <Card className="glass-card p-6 animate-fade-up">
            <h2 className="text-xl font-semibold text-foreground mb-6">
              Latest Audit Activity
            </h2>
            <div className="space-y-4">
              {recent_audits.slice(0, 10).map((audit: any) => (
                <div
                  key={audit.id}
                  className="flex items-center justify-between p-4 glass-panel rounded-xl hover:bg-muted/50 transition-all cursor-pointer"
                  onClick={() =>
                    router.push(withLocale(pathname, `/audits/${audit.id}`))
                  }
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      router.push(withLocale(pathname, `/audits/${audit.id}`));
                    }
                  }}
                  role="button"
                  tabIndex={0}
                >
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-1">
                      <h3 className="font-semibold text-foreground">
                        {audit.domain}
                      </h3>
                      <Badge
                        variant="outline"
                        className={`text-xs ${
                          audit.status === "completed"
                            ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-600"
                            : audit.status === "running"
                              ? "border-amber-500/30 bg-amber-500/10 text-amber-600"
                              : "border-red-500/30 bg-red-500/10 text-red-600"
                        }`}
                      >
                        {audit.status}
                      </Badge>
                    </div>
                    <p className="text-sm text-muted-foreground">{audit.url}</p>
                  </div>

                  <div className="flex items-center gap-6">
                    <div className="text-right">
                      <div className="text-sm text-muted-foreground">Pages</div>
                      <div className="text-lg font-semibold text-foreground">
                        {audit.total_pages}
                      </div>
                    </div>

                    <div className="text-right">
                      <div className="text-sm text-muted-foreground">
                        Issues
                      </div>
                      <div className="text-lg font-semibold text-red-500">
                        {(audit.issues.critical || 0) +
                          (audit.issues.high || 0) +
                          (audit.issues.medium || 0) +
                          (audit.issues.low || 0)}
                      </div>
                    </div>

                    {audit.status === "running" && (
                      <div className="text-right">
                        <div className="text-sm text-muted-foreground">
                          Progress
                        </div>
                        <div className="text-lg font-semibold text-amber-500">
                          {audit.progress}%
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {recent_audits.length === 0 && (
              <div className="text-center py-12 text-muted-foreground">
                <BarChart3 className="h-12 w-12 mx-auto mb-3 opacity-40" />
                <p>No audit activity yet. Run your first audit to unlock this dashboard.</p>
              </div>
            )}
          </Card>
        </div>
      </main>
    </div>
  );
}
