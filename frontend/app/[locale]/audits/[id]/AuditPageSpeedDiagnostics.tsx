"use client";

import Image from "next/image";
import { AlertTriangle } from "lucide-react";
import { formatStableDateTime, formatStableNumber } from "@/lib/dates";

type AuditPageSpeedDiagnosticsProps = {
  psData: any;
};

export default function AuditPageSpeedDiagnostics({
  psData,
}: AuditPageSpeedDiagnosticsProps) {
  return (
    <div
      className="space-y-6"
      style={{ contentVisibility: "auto", containIntrinsicSize: "1px 1200px" }}
    >
      {psData.opportunities && Object.keys(psData.opportunities).length > 0 && (
        <div className="mb-6">
          <h3 className="mb-4 text-lg font-semibold text-foreground">
            Optimization Opportunities
          </h3>
          <div className="max-h-96 space-y-2 overflow-y-auto">
            {Object.entries(psData.opportunities).map(
              ([key, data]: [string, any]) =>
                data &&
                data.score !== null &&
                data.score < 0.9 && (
                  <div
                    key={key}
                    className="flex items-start gap-3 rounded-xl border border-border bg-muted/50 p-3"
                  >
                    <AlertTriangle
                      className={`mt-1 h-4 w-4 flex-shrink-0 ${
                        data.score < 0.5 ? "text-red-500" : "text-amber-500"
                      }`}
                    />
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-medium text-foreground">
                        {data.title || key.replace(/-/g, " ")}
                      </div>
                      {data.displayValue && (
                        <div className="mt-1 text-xs text-muted-foreground">
                          {data.displayValue}
                        </div>
                      )}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      Score: {Math.round((data.score || 0) * 100)}
                    </div>
                  </div>
                ),
            )}
          </div>
        </div>
      )}

      {psData.diagnostics && Object.keys(psData.diagnostics).length > 0 && (
        <div className="mb-6">
          <h3 className="mb-4 text-lg font-semibold text-foreground">
            Diagnostics
          </h3>
          <div className="grid max-h-96 grid-cols-1 gap-3 overflow-y-auto md:grid-cols-2">
            {Object.entries(psData.diagnostics).map(
              ([key, metric]: [string, any]) =>
                metric &&
                metric.displayValue && (
                  <div
                    key={key}
                    className="rounded-xl border border-border bg-muted/50 p-3"
                  >
                    <div className="text-xs text-muted-foreground">
                      {metric.title || key.replace(/_/g, " ")}
                    </div>
                    <div className="text-sm font-medium text-foreground">
                      {metric.displayValue}
                    </div>
                    {metric.description && (
                      <div className="mt-1 text-xs text-muted-foreground">
                        {metric.description}
                      </div>
                    )}
                  </div>
                ),
            )}
          </div>
        </div>
      )}

      {psData.metadata && (
        <div className="mb-6">
          <h3 className="mb-4 text-lg font-semibold text-foreground">
            Audit Information
          </h3>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {psData.metadata.fetch_time && (
              <div className="rounded-xl border border-border bg-muted/50 p-3">
                <div className="text-xs text-muted-foreground">Fetch Time</div>
                <div className="text-sm text-foreground">
                  {formatStableDateTime(psData.metadata.fetch_time)}
                </div>
              </div>
            )}
            {psData.metadata.user_agent && (
              <div className="rounded-xl border border-border bg-muted/50 p-3">
                <div className="text-xs text-muted-foreground">User Agent</div>
                <div className="truncate text-xs text-foreground">
                  {psData.metadata.user_agent}
                </div>
              </div>
            )}
            {psData.metadata.benchmark_index !== null &&
              psData.metadata.benchmark_index !== undefined && (
                <div className="rounded-xl border border-border bg-muted/50 p-3">
                  <div className="text-xs text-muted-foreground">
                    Benchmark Index
                  </div>
                  <div className="text-sm text-foreground">
                    {psData.metadata.benchmark_index}
                  </div>
                </div>
              )}
            {psData.metadata.network_throttling && (
              <div className="rounded-xl border border-border bg-muted/50 p-3">
                <div className="text-xs text-muted-foreground">
                  Network Setting
                </div>
                <div className="truncate text-xs text-foreground">
                  {psData.metadata.network_throttling}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {psData.metrics && Object.keys(psData.metrics).length > 0 && (
        <div className="mb-6">
          <h3 className="mb-4 text-lg font-semibold text-foreground">
            Detailed Metrics
          </h3>
          <div className="grid max-h-96 grid-cols-2 gap-3 overflow-y-auto md:grid-cols-3">
            {Object.entries(psData.metrics).map(
              ([key, value]: [string, any]) => {
                if (value === null || value === undefined) {
                  return null;
                }

                let displayValue: string;
                if (typeof value === "number") {
                  if (
                    key.includes("time") ||
                    key.includes("duration") ||
                    key.includes("ms")
                  ) {
                    displayValue = `${Math.round(value)}ms`;
                  } else if (key.includes("score")) {
                    displayValue = value.toFixed(1);
                  } else {
                    displayValue = formatStableNumber(value);
                  }
                } else {
                  displayValue = String(value);
                }

                return (
                  <div
                    key={key}
                    className="rounded-xl border border-border bg-muted/50 p-3"
                  >
                    <div className="text-xs capitalize text-muted-foreground">
                      {key.replace(/_/g, " ")}
                    </div>
                    <div className="text-sm font-medium text-foreground">
                      {displayValue}
                    </div>
                  </div>
                );
              },
            )}
          </div>
        </div>
      )}

      {Array.isArray(psData.screenshots) && psData.screenshots.length > 0 && (
        <div className="mb-6">
          <h3 className="mb-4 text-lg font-semibold text-foreground">
            Page Screenshots
          </h3>
          <div className="grid grid-cols-3 gap-2 md:grid-cols-6">
            {psData.screenshots.map((screenshot: any) => (
              <div
                key={
                  screenshot.timestamp ??
                  screenshot.data ??
                  JSON.stringify(screenshot)
                }
                className="overflow-hidden rounded-lg border border-border bg-muted/50"
              >
                <div className="p-1 text-center text-[10px] text-muted-foreground">
                  {(screenshot.timestamp / 1000).toFixed(1)}s
                </div>
                {screenshot.data && (
                  <div className="relative h-24 w-full">
                    <Image
                      src={screenshot.data}
                      alt={`Screenshot at ${screenshot.timestamp}ms`}
                      fill
                      sizes="160px"
                      className="object-cover object-top"
                    />
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {psData.audits && Object.keys(psData.audits).length > 0 && (
        <div className="mb-6">
          <h3 className="mb-4 text-lg font-semibold text-foreground">
            Improvement Recommendations
          </h3>
          <div className="max-h-[500px] space-y-3 overflow-y-auto">
            {Object.entries(psData.audits).map(
              ([key, audit]: [string, any]) => {
                if (!audit || !audit.title) {
                  return null;
                }

                const isPass = audit.scoreDisplayMode === "pass";
                const score =
                  audit.score !== null && audit.score !== undefined
                    ? audit.score
                    : null;

                return (
                  <div
                    key={key}
                    className={`rounded-xl border p-4 ${
                      isPass
                        ? "border-green-500/20 bg-green-500/5"
                        : "border-yellow-500/20 bg-yellow-500/5"
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="mb-2 flex items-start justify-between gap-2">
                          <h4 className="font-medium text-foreground">
                            {audit.title}
                          </h4>
                          {score !== null && (
                            <div
                              className={`rounded px-2 py-1 text-xs font-bold ${
                                isPass
                                  ? "bg-green-500/20 text-green-300"
                                  : score >= 0.75
                                    ? "bg-yellow-500/20 text-yellow-300"
                                    : "bg-red-500/20 text-red-300"
                              }`}
                            >
                              {Math.round(score * 100)}
                            </div>
                          )}
                        </div>
                        {audit.description && (
                          <p className="mb-2 text-sm text-muted-foreground">
                            {audit.description}
                          </p>
                        )}
                        {audit.explanation && (
                          <div className="mb-2 rounded bg-black/20 p-2 text-xs text-muted-foreground">
                            {audit.explanation}
                          </div>
                        )}
                        {audit.details?.type === "opportunity" &&
                          Array.isArray(audit.details.items) && (
                            <div className="text-xs text-muted-foreground">
                              <div className="mb-1 font-medium">
                                Savings:{" "}
                                {audit.details.headings?.[0]?.valueType ===
                                "timespanMs"
                                  ? "Time"
                                  : "Bytes"}
                              </div>
                              <div className="space-y-1">
                                {audit.details.items
                                  .slice(0, 3)
                                  .map((item: any) => (
                                    <div
                                      key={
                                        item.url ??
                                        item.source ??
                                        JSON.stringify(item)
                                      }
                                      className="text-xs"
                                    >
                                      *{" "}
                                      {item.url ||
                                        item.source ||
                                        JSON.stringify(item).substring(0, 100)}
                                    </div>
                                  ))}
                                {audit.details.items.length > 3 && (
                                  <div className="text-xs">
                                    ... and {audit.details.items.length - 3}{" "}
                                    more
                                  </div>
                                )}
                              </div>
                            </div>
                          )}
                      </div>
                    </div>
                  </div>
                );
              },
            )}
          </div>
        </div>
      )}
    </div>
  );
}
