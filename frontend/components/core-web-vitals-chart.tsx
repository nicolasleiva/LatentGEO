"use client";

import Image from "next/image";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "@/components/recharts-dynamic";

interface CoreWebVitalsProps {
  data: any;
}

interface MetricCardProps {
  label: string;
  value: string;
  sub: string;
}

interface MetricsPayload {
  fcp: number;
  lcp: number;
  tbt: number;
  cls: number;
  si: number;
}

function MetricsRow({ metrics, sub }: { metrics: MetricsPayload; sub: string }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
      <MetricCard label="FCP" value={`${(metrics.fcp / 1000).toFixed(1)}s`} sub={sub} />
      <MetricCard label="LCP" value={`${(metrics.lcp / 1000).toFixed(1)}s`} sub={sub} />
      <MetricCard label="TBT" value={`${metrics.tbt.toFixed(0)}ms`} sub={sub} />
      <MetricCard label="CLS" value={metrics.cls.toFixed(3)} sub={sub} />
      <MetricCard label="SI" value={`${(metrics.si / 1000).toFixed(1)}s`} sub={sub} />
    </div>
  );
}

function MetricCard({ label, value, sub }: MetricCardProps) {
  return (
    <div className="text-center p-4 glass-panel border border-border rounded-xl hover:bg-muted/50 transition-colors">
      <div className="text-xs text-muted-foreground uppercase tracking-wider mb-1">{label}</div>
      <div className="text-xl font-semibold text-foreground">{value}</div>
      <div className="text-xs text-muted-foreground/70 mt-1">{sub}</div>
    </div>
  );
}

function TestInformationSection({
  mobile,
  desktop,
  formatDate,
}: {
  mobile: any;
  desktop: any;
  formatDate: (isoString: string) => string;
}) {
  if (!mobile?.metadata) {
    return null;
  }

  return (
    <div className="glass p-6 rounded-2xl">
      <h3 className="text-lg font-medium mb-6 text-foreground">Test Information</h3>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8 text-sm">
        <div>
          <div className="font-semibold mb-3 text-muted-foreground border-b border-border pb-2">
            Mobile
          </div>
          <div className="space-y-2 text-muted-foreground">
            <div className="flex justify-between">
              <span>Captured:</span> <span>{formatDate(mobile.metadata.fetch_time)}</span>
            </div>
            <div className="flex justify-between">
              <span>Device:</span> <span>Moto G Power (Emulated)</span>
            </div>
            <div className="flex justify-between">
              <span>Lighthouse:</span> <span>{mobile.metadata.lighthouse_version}</span>
            </div>
            <div className="flex justify-between">
              <span>Network:</span> <span>4G Throttling</span>
            </div>
          </div>
        </div>

        {desktop?.metadata && (
          <div>
            <div className="font-semibold mb-3 text-muted-foreground border-b border-border pb-2">
              Desktop
            </div>
            <div className="space-y-2 text-muted-foreground">
              <div className="flex justify-between">
                <span>Captured:</span> <span>{formatDate(desktop.metadata.fetch_time)}</span>
              </div>
              <div className="flex justify-between">
                <span>Device:</span> <span>Desktop Browser</span>
              </div>
              <div className="flex justify-between">
                <span>Lighthouse:</span> <span>{desktop.metadata.lighthouse_version}</span>
              </div>
              <div className="flex justify-between">
                <span>Network:</span> <span>Simulated</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function DetailedMetricsSection({ mobile, desktop }: { mobile: any; desktop: any }) {
  if (!mobile?.metrics) {
    return null;
  }

  return (
    <div className="glass p-6 rounded-2xl">
      <h3 className="text-lg font-medium mb-6 text-foreground">Detailed Metrics</h3>
      <MetricsRow metrics={mobile.metrics} sub="Mobile" />
      {desktop?.metrics && (
        <div className="mt-4">
          <MetricsRow metrics={desktop.metrics} sub="Desktop" />
        </div>
      )}
    </div>
  );
}

function ScreenshotPanel({
  title,
  screenshots,
  desktop = false,
}: {
  title: string;
  screenshots: any[];
  desktop?: boolean;
}) {
  if (!screenshots || screenshots.length === 0) {
    return null;
  }

  return (
    <div className="glass p-6 rounded-2xl">
      <h3 className="text-lg font-medium mb-6 text-foreground">{title}</h3>
      <div className="grid grid-cols-4 md:grid-cols-6 gap-2">
        {screenshots.map((shot: any, idx: number) => (
          <div
            key={shot.timestamp || shot.data || shot.filename || `${title}-${idx}`}
            className="border border-border rounded-lg overflow-hidden bg-background/70"
          >
            <Image
              src={shot.data}
              alt={`Screenshot ${idx + 1}`}
              className={
                desktop
                  ? "w-full h-auto max-h-20 object-cover object-top"
                  : "w-full h-auto"
              }
              width={desktop ? 160 : 120}
              height={desktop ? 80 : 90}
              unoptimized
            />
            <div className="text-[10px] text-center p-1 text-muted-foreground">
              {(shot.timestamp / 1000).toFixed(1)}s
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function LighthouseScoresSection({ scoresData }: { scoresData: any[] }) {
  return (
    <div className="glass p-6 rounded-2xl flex flex-col">
      <h3 className="text-lg font-medium mb-6 text-foreground">Lighthouse Scores</h3>
      <div className="flex-1 min-h-[300px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={scoresData}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
            <XAxis
              dataKey="metric"
              stroke="hsl(var(--muted-foreground))"
              tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              domain={[0, 100]}
              stroke="hsl(var(--muted-foreground))"
              tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "hsl(var(--background))",
                borderColor: "hsl(var(--border))",
                color: "hsl(var(--foreground))",
                borderRadius: "12px",
                backdropFilter: "blur(10px)",
              }}
              itemStyle={{ color: "hsl(var(--foreground))" }}
              cursor={{ fill: "hsl(var(--accent))" }}
            />
            <Legend wrapperStyle={{ color: "hsl(var(--muted-foreground))" }} />
            <Bar dataKey="Mobile" fill="#0f766e" radius={[4, 4, 0, 0]} />
            <Bar dataKey="Desktop" fill="#14b8a6" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function CoreVitalsSection({ vitalsData }: { vitalsData: any[] }) {
  return (
    <div className="glass p-6 rounded-2xl">
      <h3 className="text-lg font-medium mb-6 text-foreground">Core Web Vitals</h3>
      <div className="space-y-4">
        {vitalsData.map((item) => (
          <div key={item.metric} className="border-b border-border/70 pb-4 last:border-0">
            <div className="flex justify-between items-center mb-2">
              <span className="font-semibold text-sm text-foreground">{item.metric}</span>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="text-xs text-muted-foreground mb-1">Mobile</div>
                <div className="text-2xl font-semibold text-foreground">{item.Mobile}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground mb-1">Desktop</div>
                <div className="text-2xl font-semibold text-foreground">{item.Desktop}</div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function OpportunitiesSection({
  mobile,
  desktop,
}: {
  mobile: any;
  desktop: any;
}) {
  if (!mobile?.opportunities && !desktop?.opportunities) {
    return null;
  }

  const renderList = (title: string, items: any) => (
    <div className="glass p-6 rounded-2xl">
      <h3 className="text-lg font-medium mb-6 text-foreground">{title}</h3>
      <div className="space-y-3 text-sm">
        {Object.entries(items).map(([key, audit]: [string, any]) =>
          audit?.title ? (
            <div
              key={key}
              className="flex justify-between border-b border-border/70 pb-2 last:border-0"
            >
              <span className="text-muted-foreground">{audit.title}</span>
              <span className="font-semibold text-foreground">
                {audit.displayValue || (audit.score === 1 ? "OK" : "Improve")}
              </span>
            </div>
          ) : null,
        )}
      </div>
    </div>
  );

  return (
    <div className="grid gap-6 md:grid-cols-2">
      {mobile?.opportunities && renderList("Opportunities (Mobile)", mobile.opportunities)}
      {desktop?.opportunities && renderList("Opportunities (Desktop)", desktop.opportunities)}
    </div>
  );
}

export function CoreWebVitalsChart({ data }: CoreWebVitalsProps) {
  const mobile = data.mobile || (data.performance_score !== undefined ? data : null);
  const desktop = data.desktop || null;

  const scoresData = [
    {
      metric: "Performance",
      Mobile: mobile?.performance_score || 0,
      Desktop: desktop?.performance_score || 0,
    },
    {
      metric: "Accessibility",
      Mobile: mobile?.accessibility_score || 0,
      Desktop: desktop?.accessibility_score || 0,
    },
    {
      metric: "Best Practices",
      Mobile: mobile?.best_practices_score || 0,
      Desktop: desktop?.best_practices_score || 0,
    },
    {
      metric: "SEO",
      Mobile: mobile?.seo_score || 0,
      Desktop: desktop?.seo_score || 0,
    },
  ];

  const vitalsData = [
    {
      metric: "LCP (s)",
      Mobile: ((mobile?.core_web_vitals?.lcp || 0) / 1000).toFixed(2),
      Desktop: ((desktop?.core_web_vitals?.lcp || 0) / 1000).toFixed(2),
    },
    {
      metric: "FID (ms)",
      Mobile: (mobile?.core_web_vitals?.fid || 0).toFixed(0),
      Desktop: (desktop?.core_web_vitals?.fid || 0).toFixed(0),
    },
    {
      metric: "CLS (x100)",
      Mobile: ((mobile?.core_web_vitals?.cls || 0) * 100).toFixed(2),
      Desktop: ((desktop?.core_web_vitals?.cls || 0) * 100).toFixed(2),
    },
    {
      metric: "FCP (s)",
      Mobile: ((mobile?.core_web_vitals?.fcp || 0) / 1000).toFixed(2),
      Desktop: ((desktop?.core_web_vitals?.fcp || 0) / 1000).toFixed(2),
    },
  ];

  const formatDate = (isoString: string) => {
    if (!isoString) return "N/A";
    return new Date(isoString).toLocaleString("en-US", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      timeZoneName: "short",
    });
  };

  return (
    <div className="space-y-8">
      <TestInformationSection mobile={mobile} desktop={desktop} formatDate={formatDate} />
      <DetailedMetricsSection mobile={mobile} desktop={desktop} />

      <div className="grid gap-6 md:grid-cols-2">
        <ScreenshotPanel title="Loading Screenshots (Mobile)" screenshots={mobile?.screenshots || []} />
        <ScreenshotPanel
          title="Loading Screenshots (Desktop)"
          screenshots={desktop?.screenshots || []}
          desktop
        />
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <LighthouseScoresSection scoresData={scoresData} />
        <CoreVitalsSection vitalsData={vitalsData} />
      </div>

      <OpportunitiesSection mobile={mobile} desktop={desktop} />
    </div>
  );
}
