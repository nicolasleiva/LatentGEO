"use client";

import { useEffect, useMemo, useReducer, useState } from "react";
import {
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  AreaChart,
  Area,
} from "@/components/recharts-dynamic";
import { Calendar, BarChart3, ArrowUpRight, ArrowDownRight } from "lucide-react";
import { API_URL } from "@/lib/api";
import { fetchWithBackendAuth } from "@/lib/backend-auth";

interface ScoreHistoryProps {
  domain: string;
}

interface ComparisonMetric {
  current: number;
  previous: number;
  change: number;
  change_pct: number;
  trend: "up" | "down" | "stable";
}

interface MonthlyComparison {
  domain: string;
  current_month: string;
  previous_month: string;
  comparison: {
    overall_score: ComparisonMetric;
    seo_score: ComparisonMetric;
    geo_score: ComparisonMetric;
    performance_score: ComparisonMetric;
    lcp: ComparisonMetric;
    critical_issues: ComparisonMetric;
    audit_count: ComparisonMetric;
  };
}

interface ComparisonCardProps {
  label: string;
  metric: ComparisonMetric;
  isLowerBetter?: boolean;
}

interface ScoreHistoryViewState {
  history: any[];
  comparison: MonthlyComparison | null;
  loading: boolean;
}

type ScoreHistoryViewAction =
  | { type: "reset" }
  | { type: "start" }
  | { type: "loaded"; history: any[]; comparison: MonthlyComparison | null }
  | { type: "error" };

function scoreHistoryViewReducer(
  state: ScoreHistoryViewState,
  action: ScoreHistoryViewAction,
): ScoreHistoryViewState {
  switch (action.type) {
    case "reset":
      return { history: [], comparison: null, loading: false };
    case "start":
      return { ...state, loading: true };
    case "loaded":
      return {
        history: action.history,
        comparison: action.comparison,
        loading: false,
      };
    case "error":
      return { ...state, loading: false };
    default:
      return state;
  }
}

function ComparisonCard({
  label,
  metric,
  isLowerBetter = false,
}: ComparisonCardProps) {
  const isPositive = isLowerBetter ? metric.change < 0 : metric.change > 0;
  const colorClass =
    metric.trend === "stable"
      ? "text-muted-foreground"
      : isPositive
        ? "text-green-500"
        : "text-red-500";

  return (
    <div className="p-4 glass-panel rounded-xl border border-border hover:bg-muted/50 transition-colors">
      <div className="text-xs text-muted-foreground uppercase tracking-wider mb-2">
        {label}
      </div>
      <div className="flex items-baseline gap-2">
        <span className="text-2xl font-bold text-foreground">{metric.current}</span>
        <span className={`text-sm ${colorClass} flex items-center gap-1`}>
          {metric.trend === "up" && <ArrowUpRight className="w-3 h-3" />}
          {metric.trend === "down" && <ArrowDownRight className="w-3 h-3" />}
          {metric.change > 0 ? "+" : ""}
          {metric.change_pct}%
        </span>
      </div>
      <div className="text-xs text-muted-foreground mt-1">vs {metric.previous} previous month</div>
    </div>
  );
}

function MonthlyComparisonSection({ comparison }: { comparison: MonthlyComparison }) {
  return (
    <div className="glass-card p-6 rounded-2xl">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-brand/10 rounded-lg">
            <Calendar className="w-5 h-5 text-brand" />
          </div>
          <div>
            <h3 className="text-lg font-medium text-foreground">Monthly Comparison</h3>
            <p className="text-sm text-muted-foreground">
              {comparison.current_month} vs {comparison.previous_month}
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <ComparisonCard label="Overall Score" metric={comparison.comparison.overall_score} />
        <ComparisonCard label="SEO Score" metric={comparison.comparison.seo_score} />
        <ComparisonCard label="GEO Score" metric={comparison.comparison.geo_score} />
        <ComparisonCard label="Performance" metric={comparison.comparison.performance_score} />
        <ComparisonCard label="LCP (ms)" metric={comparison.comparison.lcp} isLowerBetter />
        <ComparisonCard
          label="Critical issues"
          metric={comparison.comparison.critical_issues}
          isLowerBetter
        />
        <ComparisonCard label="Audits" metric={comparison.comparison.audit_count} />
      </div>
    </div>
  );
}

function HistoryChartSection({
  domain,
  days,
  setDays,
  formattedHistory,
}: {
  domain: string;
  days: number;
  setDays: (value: number) => void;
  formattedHistory: any[];
}) {
  return (
    <div className="glass-card p-6 rounded-2xl">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-brand/10 rounded-lg">
            <BarChart3 className="w-5 h-5 text-brand" />
          </div>
          <div>
            <h3 className="text-lg font-medium text-foreground">Score history</h3>
            <p className="text-sm text-muted-foreground">{domain}</p>
          </div>
        </div>

        <div className="flex gap-2">
          {[30, 60, 90].map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={`px-3 py-1 text-sm rounded-lg transition-colors ${
                days === d
                  ? "bg-muted text-foreground"
                  : "glass-panel text-muted-foreground hover:bg-muted/50"
              }`}
            >
              {d}d
            </button>
          ))}
        </div>
      </div>

      {formattedHistory.length > 0 ? (
        <div className="h-[300px]">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={formattedHistory}>
              <defs>
                <linearGradient id="colorOverall" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="hsl(var(--brand))" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="hsl(var(--brand))" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="colorSeo" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#14b8a6" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#14b8a6" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="colorGeo" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#334155" stopOpacity={0.25} />
                  <stop offset="95%" stopColor="#334155" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis
                dataKey="date"
                stroke="hsl(var(--muted-foreground))"
                tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
              />
              <YAxis
                domain={[0, 100]}
                stroke="hsl(var(--muted-foreground))"
                tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "hsl(var(--background))",
                  borderColor: "hsl(var(--border))",
                  borderRadius: "12px",
                  color: "hsl(var(--foreground))",
                  backdropFilter: "blur(10px)",
                }}
              />
              <Legend wrapperStyle={{ color: "hsl(var(--muted-foreground))" }} />
              <Area
                type="monotone"
                dataKey="overall_score"
                name="Overall"
                stroke="hsl(var(--brand))"
                fillOpacity={1}
                fill="url(#colorOverall)"
              />
              <Area
                type="monotone"
                dataKey="seo_score"
                name="SEO"
                stroke="#14b8a6"
                fillOpacity={1}
                fill="url(#colorSeo)"
              />
              <Area
                type="monotone"
                dataKey="geo_score"
                name="GEO"
                stroke="#334155"
                fillOpacity={1}
                fill="url(#colorGeo)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className="h-[300px] flex items-center justify-center border border-dashed border-border rounded-xl">
          <div className="text-center">
            <BarChart3 className="w-12 h-12 text-muted-foreground/50 mx-auto mb-4" />
            <p className="text-muted-foreground">No historical data available</p>
            <p className="text-muted-foreground/70 text-sm mt-2">
              Data is automatically recorded with each audit
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

function HistoryTableSection({ formattedHistory }: { formattedHistory: any[] }) {
  if (formattedHistory.length === 0) {
    return null;
  }

  return (
    <div className="glass-card p-6 rounded-2xl">
      <h3 className="text-lg font-medium text-foreground mb-4">Audit details</h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border">
              <th className="text-left py-3 px-4 text-muted-foreground font-medium">Date</th>
              <th className="text-center py-3 px-4 text-muted-foreground font-medium">Overall</th>
              <th className="text-center py-3 px-4 text-muted-foreground font-medium">SEO</th>
              <th className="text-center py-3 px-4 text-muted-foreground font-medium">GEO</th>
              <th className="text-center py-3 px-4 text-muted-foreground font-medium">Performance</th>
              <th className="text-center py-3 px-4 text-muted-foreground font-medium">Issues</th>
            </tr>
          </thead>
          <tbody>
            {formattedHistory
              .slice(-10)
              .reverse()
              .map((h) => (
                <tr key={`${h.date}-${h.overall_score}`} className="border-b border-border hover:bg-muted/50">
                  <td className="py-3 px-4 text-foreground">{h.date}</td>
                  <td className="py-3 px-4 text-center">
                    <span
                      className={`font-medium ${
                        h.overall_score >= 70
                          ? "text-green-500"
                          : h.overall_score >= 50
                            ? "text-yellow-500"
                            : "text-red-500"
                      }`}
                    >
                      {h.overall_score}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-center text-foreground">{h.seo_score}</td>
                  <td className="py-3 px-4 text-center text-foreground">{h.geo_score}</td>
                  <td className="py-3 px-4 text-center text-foreground">{h.performance_score}</td>
                  <td className="py-3 px-4 text-center">
                    <span className="text-red-500">{h.critical_issues}</span>
                    <span className="text-muted-foreground mx-1">/</span>
                    <span className="text-orange-500">{h.high_issues}</span>
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function ScoreHistoryChart({ domain }: ScoreHistoryProps) {
  const [viewState, dispatch] = useReducer(scoreHistoryViewReducer, {
    history: [],
    comparison: null,
    loading: true,
  });
  const [days, setDays] = useState(90);

  useEffect(() => {
    if (!domain) {
      dispatch({ type: "reset" });
      return;
    }

    const fetchData = async () => {
      dispatch({ type: "start" });
      try {
        const params = new URLSearchParams({ days: days.toString() });

        const [historyRes, comparisonRes] = await Promise.all([
          fetchWithBackendAuth(
            `${API_URL}/api/v1/score-history/domain/${encodeURIComponent(domain)}?${params}`,
          ),
          fetchWithBackendAuth(
            `${API_URL}/api/v1/score-history/domain/${encodeURIComponent(domain)}/comparison`,
          ),
        ]);

        const history = historyRes.ok ? (await historyRes.json()).history || [] : [];
        const comparison = comparisonRes.ok ? await comparisonRes.json() : null;

        dispatch({ type: "loaded", history, comparison });
      } catch (error) {
        console.error("Error fetching score history:", error);
        dispatch({ type: "error" });
      }
    };

    fetchData();
  }, [domain, days]);

  const formattedHistory = useMemo(
    () =>
      viewState.history.map((h) => ({
        ...h,
        date: new Date(h.recorded_at).toLocaleDateString("en-US", {
          month: "short",
          day: "numeric",
        }),
      })),
    [viewState.history],
  );

  if (viewState.loading) {
    return (
      <div className="p-8 text-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-foreground mx-auto"></div>
        <p className="text-muted-foreground mt-4">Loading history...</p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {viewState.comparison && <MonthlyComparisonSection comparison={viewState.comparison} />}
      <HistoryChartSection
        domain={domain}
        days={days}
        setDays={setDays}
        formattedHistory={formattedHistory}
      />
      <HistoryTableSection formattedHistory={formattedHistory} />
    </div>
  );
}
