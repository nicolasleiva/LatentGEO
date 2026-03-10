"use client";

import { RefreshCw, Target } from "lucide-react";
import { Button } from "@/components/ui/button";

type AuditFixPlanTabProps = {
  fixPlanLoading: boolean;
  fixPlan: any[] | null;
  fixPlanMessage: string | null;
  fallbackMessage: string;
  onRefresh: () => void;
};

export default function AuditFixPlanTab({
  fixPlanLoading,
  fixPlan,
  fixPlanMessage,
  fallbackMessage,
  onRefresh,
}: AuditFixPlanTabProps) {
  return (
    <div
      className="glass-card p-8"
      style={{ contentVisibility: "auto", containIntrinsicSize: "1px 720px" }}
    >
      <div className="mb-6 flex items-center justify-between gap-4">
        <h2 className="flex items-center gap-3 text-2xl font-bold text-foreground">
          <Target className="h-6 w-6 text-brand" />
          Execution Plan
        </h2>
        <Button variant="outline" onClick={onRefresh}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Refresh
        </Button>
      </div>

      {fixPlanLoading ? (
        <div className="flex items-center gap-2 text-muted-foreground">
          <RefreshCw className="h-4 w-4 animate-spin" />
          Loading execution plan...
        </div>
      ) : fixPlan && fixPlan.length > 0 ? (
        <div className="space-y-3">
          {fixPlan.map((item: any, idx: number) => (
            <div
              key={item?.title ?? item?.issue ?? JSON.stringify(item)}
              className="rounded-xl border border-border bg-muted/40 p-4"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="text-sm font-semibold text-foreground">
                    {item?.title || item?.issue || `Fix #${idx + 1}`}
                  </div>
                  {item?.description && (
                    <div className="mt-1 text-sm text-muted-foreground break-words whitespace-pre-wrap">
                      {item.description}
                    </div>
                  )}
                </div>
                {item?.priority && (
                  <span className="rounded-full border border-border px-2 py-1 text-xs capitalize text-muted-foreground">
                    {item.priority}
                  </span>
                )}
              </div>
              {(item?.files || item?.recommendations || item?.steps) && (
                <pre className="mt-3 overflow-auto rounded-lg border border-border bg-muted/30 p-3 text-xs">
                  {JSON.stringify(
                    {
                      files: item.files,
                      recommendations: item.recommendations,
                      steps: item.steps,
                    },
                    null,
                    2,
                  )}
                </pre>
              )}
            </div>
          ))}
        </div>
      ) : (
        <div className="text-muted-foreground">
          {fixPlanMessage || fallbackMessage}
        </div>
      )}
    </div>
  );
}
