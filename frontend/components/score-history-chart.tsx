"use client";

import { useEffect, useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  AreaChart,
  Area,
} from "recharts";
import {
  TrendingUp,
  TrendingDown,
  Minus,
  Calendar,
  BarChart3,
  ArrowUpRight,
  ArrowDownRight,
} from "lucide-react";
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

export function ScoreHistoryChart({ domain }: ScoreHistoryProps) {
  const [history, setHistory] = useState<any[]>([]);
  const [comparison, setComparison] = useState<MonthlyComparison | null>(null);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(90);

  const backendUrl = API_URL;

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const params = new URLSearchParams({ days: days.toString() });

        const [historyRes, comparisonRes] = await Promise.all([
          fetchWithBackendAuth(
            `${backendUrl}/api/score-history/domain/${encodeURIComponent(domain)}?${params}`,
          ),
          fetchWithBackendAuth(
            `${backendUrl}/api/score-history/domain/${encodeURIComponent(domain)}/comparison`,
          ),
        ]);

        if (historyRes.ok) {
          const data = await historyRes.json();
          setHistory(data.history || []);
        }

        if (comparisonRes.ok) {
          const data = await comparisonRes.json();
          setComparison(data);
        }
      } catch (error) {
        console.error("Error fetching score history:", error);
      } finally {
        setLoading(false);
      }
    };

    if (domain) fetchData();
  }, [domain, days, backendUrl]);

  const TrendIcon = ({ trend }: { trend: "up" | "down" | "stable" }) => {
    if (trend === "up")
      return <TrendingUp className="w-4 h-4 text-green-400" />;
    if (trend === "down")
      return <TrendingDown className="w-4 h-4 text-red-400" />;
    return <Minus className="w-4 h-4 text-muted-foreground" />;
  };

  const ComparisonCard = ({
    label,
    metric,
    isLowerBetter = false,
  }: {
    label: string;
    metric: ComparisonMetric;
    isLowerBetter?: boolean;
  }) => {
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
          <span className="text-2xl font-bold text-foreground">
            {metric.current}
          </span>
          <span className={`text-sm ${colorClass} flex items-center gap-1`}>
            {metric.trend === "up" && <ArrowUpRight className="w-3 h-3" />}
            {metric.trend === "down" && <ArrowDownRight className="w-3 h-3" />}
            {metric.change > 0 ? "+" : ""}
            {metric.change_pct}%
          </span>
        </div>
        <div className="text-xs text-muted-foreground mt-1">
          vs {metric.previous} previous month
        </div>
      </div>
    );
  };

  if (loading) {
    return (
      <div className="p-8 text-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-foreground mx-auto"></div>
        <p className="text-muted-foreground mt-4">Loading history...</p>
      </div>
    );
  }

  const formattedHistory = history.map((h) => ({
    ...h,
    date: new Date(h.recorded_at).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
    }),
  }));

  return (
    <div className="space-y-8">
      {/* Monthly Comparison */}
      {comparison && (
        <div className="glass-card p-6 rounded-2xl">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-brand/10 rounded-lg">
                <Calendar className="w-5 h-5 text-brand" />
              </div>
              <div>
                <h3 className="text-lg font-medium text-foreground">
                  Monthly Comparison
                </h3>
                <p className="text-sm text-muted-foreground">
                  {comparison.current_month} vs {comparison.previous_month}
                </p>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <ComparisonCard
              label="Overall Score"
              metric={comparison.comparison.overall_score}
            />
            <ComparisonCard
              label="SEO Score"
              metric={comparison.comparison.seo_score}
            />
            <ComparisonCard
              label="GEO Score"
              metric={comparison.comparison.geo_score}
            />
            <ComparisonCard
              label="Performance"
              metric={comparison.comparison.performance_score}
            />
            <ComparisonCard
              label="LCP (ms)"
              metric={comparison.comparison.lcp}
              isLowerBetter
            />
            <ComparisonCard
              label="Critical issues"
              metric={comparison.comparison.critical_issues}
              isLowerBetter
            />
            <ComparisonCard
              label="Audits"
              metric={comparison.comparison.audit_count}
            />
          </div>
        </div>
      )}

      {/* History chart */}
      <div className="glass-card p-6 rounded-2xl">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-brand/10 rounded-lg">
              <BarChart3 className="w-5 h-5 text-brand" />
            </div>
            <div>
              <h3 className="text-lg font-medium text-foreground">
                Score history
              </h3>
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
                    <stop
                      offset="5%"
                      stopColor="hsl(var(--brand))"
                      stopOpacity={0.3}
                    />
                    <stop
                      offset="95%"
                      stopColor="hsl(var(--brand))"
                      stopOpacity={0}
                    />
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
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="hsl(var(--border))"
                />
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
                <Legend
                  wrapperStyle={{ color: "hsl(var(--muted-foreground))" }}
                />
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
              <p className="text-muted-foreground">
                No historical data available
              </p>
              <p className="text-muted-foreground/70 text-sm mt-2">
                Data is automatically recorded with each audit
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Detailed history table */}
      {formattedHistory.length > 0 && (
        <div className="glass-card p-6 rounded-2xl">
          <h3 className="text-lg font-medium text-foreground mb-4">
            Audit details
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left py-3 px-4 text-muted-foreground font-medium">
                    Date
                  </th>
                  <th className="text-center py-3 px-4 text-muted-foreground font-medium">
                    Overall
                  </th>
                  <th className="text-center py-3 px-4 text-muted-foreground font-medium">
                    SEO
                  </th>
                  <th className="text-center py-3 px-4 text-muted-foreground font-medium">
                    GEO
                  </th>
                  <th className="text-center py-3 px-4 text-muted-foreground font-medium">
                    Performance
                  </th>
                  <th className="text-center py-3 px-4 text-muted-foreground font-medium">
                    Issues
                  </th>
                </tr>
              </thead>
              <tbody>
                {formattedHistory
                  .slice(-10)
                  .reverse()
                  .map((h, idx) => (
                    <tr
                      key={idx}
                      className="border-b border-border hover:bg-muted/50"
                    >
                      <td className="py-3 px-4 text-foreground">{h.date}</td>
                      <td className="py-3 px-4 text-center">
                        <span
                          className={`font-medium ${h.overall_score >= 70 ? "text-green-500" : h.overall_score >= 50 ? "text-yellow-500" : "text-red-500"}`}
                        >
                          {h.overall_score}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-center text-foreground">
                        {h.seo_score}
                      </td>
                      <td className="py-3 px-4 text-center text-foreground">
                        {h.geo_score}
                      </td>
                      <td className="py-3 px-4 text-center text-foreground">
                        {h.performance_score}
                      </td>
                      <td className="py-3 px-4 text-center">
                        <span className="text-red-500">
                          {h.critical_issues}
                        </span>
                        <span className="text-muted-foreground mx-1">/</span>
                        <span className="text-orange-500">{h.high_issues}</span>
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
