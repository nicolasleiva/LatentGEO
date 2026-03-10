"use client";

import { AlertCircle, AlertTriangle, Info, Wrench } from "lucide-react";

export type RuntimeDiagnosticEntry = {
  source?: string | null;
  stage?: string | null;
  severity?: "error" | "warning" | "info" | string | null;
  code?: string | null;
  message?: string | null;
  technical_detail?: string | null;
  created_at?: string | null;
};

type AuditPipelineDiagnosticsProps = {
  diagnostics?: RuntimeDiagnosticEntry[] | null;
  errorMessage?: string | null;
  title?: string;
  className?: string;
};

const severityConfig = {
  error: {
    badge: "border-red-500/30 bg-red-500/10 text-red-700",
    icon: AlertCircle,
    iconClassName: "text-red-600",
    card: "border-red-500/20 bg-red-500/5",
  },
  warning: {
    badge: "border-amber-500/30 bg-amber-500/10 text-amber-700",
    icon: AlertTriangle,
    iconClassName: "text-amber-600",
    card: "border-amber-500/20 bg-amber-500/5",
  },
  info: {
    badge: "border-blue-500/30 bg-blue-500/10 text-blue-700",
    icon: Info,
    iconClassName: "text-blue-600",
    card: "border-blue-500/20 bg-blue-500/5",
  },
} as const;

const formatTimestamp = (value?: string | null) => {
  if (!value) return "Recent";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "Recent";
  return `${parsed.toISOString().slice(0, 16).replace("T", " ")} UTC`;
};

const humanize = (value?: string | null) => {
  const cleaned = String(value || "")
    .replace(/[_-]+/g, " ")
    .trim();
  if (!cleaned) return "pipeline";
  return cleaned.replace(/\b\w/g, (char) => char.toUpperCase());
};

export function AuditPipelineDiagnostics({
  diagnostics,
  errorMessage,
  title = "Pipeline Diagnostics",
  className = "",
}: AuditPipelineDiagnosticsProps) {
  const normalizedDiagnostics = Array.isArray(diagnostics)
    ? diagnostics.filter((entry) => entry && entry.message)
    : [];

  const entries =
    normalizedDiagnostics.length > 0
      ? normalizedDiagnostics
      : errorMessage
        ? [
            {
              source: "pipeline",
              stage: "audit-status-update",
              severity: "error",
              code: "audit_error_message",
              message: errorMessage,
            } satisfies RuntimeDiagnosticEntry,
          ]
        : [];

  if (entries.length === 0) {
    return null;
  }

  return (
    <section
      data-testid="pipeline-diagnostics"
      className={`glass-card rounded-2xl p-6 ${className}`.trim()}
    >
      <div className="mb-5 flex items-center gap-3">
        <div className="rounded-xl bg-amber-500/10 p-3">
          <Wrench className="h-5 w-5 text-amber-600" />
        </div>
        <div>
          <h2 className="text-xl font-semibold text-foreground">{title}</h2>
          <p className="text-sm text-muted-foreground">
            Persistent warnings and failures from PDF, PageSpeed, GEO, and the
            audit pipeline.
          </p>
        </div>
      </div>

      <div className="space-y-3">
        {entries.map((entry, index) => {
          const severity =
            entry.severity === "error" || entry.severity === "warning"
              ? entry.severity
              : "info";
          const config = severityConfig[severity];
          const Icon = config.icon;
          return (
            <div
              key={`${entry.code || entry.message || "diagnostic"}-${index}`}
              className={`rounded-2xl border p-4 ${config.card}`}
            >
              <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div className="min-w-0 flex-1">
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <span
                      className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11px] font-medium uppercase tracking-wide ${config.badge}`}
                    >
                      <Icon className={`h-3.5 w-3.5 ${config.iconClassName}`} />
                      {severity}
                    </span>
                    <span className="rounded-full border border-border bg-muted/40 px-2.5 py-1 text-[11px] uppercase tracking-wide text-muted-foreground">
                      {humanize(entry.source)}
                    </span>
                    <span className="rounded-full border border-border bg-muted/40 px-2.5 py-1 text-[11px] uppercase tracking-wide text-muted-foreground">
                      {humanize(entry.stage)}
                    </span>
                  </div>

                  <p className="text-sm font-medium leading-6 text-foreground">
                    {entry.message}
                  </p>

                  {entry.technical_detail ? (
                    <details className="mt-3 text-xs text-muted-foreground">
                      <summary className="cursor-pointer select-none">
                        Technical detail
                      </summary>
                      <p className="mt-2 rounded-xl border border-border bg-muted/40 p-3 leading-5">
                        {entry.technical_detail}
                      </p>
                    </details>
                  ) : null}
                </div>

                <div className="text-xs text-muted-foreground">
                  {formatTimestamp(entry.created_at)}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

export default AuditPipelineDiagnostics;
