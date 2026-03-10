"use client";

import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";

type AuditPageFindingsSectionProps = {
  pages: any[];
  visiblePages: any[];
  remainingCount: number;
  onLoadAll: () => void;
};

export default function AuditPageFindingsSection({
  pages,
  visiblePages,
  remainingCount,
  onLoadAll,
}: AuditPageFindingsSectionProps) {
  return (
    <div
      className="mb-8 rounded-3xl border border-border/70 bg-card p-8 shadow-sm"
      style={{ contentVisibility: "auto", containIntrinsicSize: "1px 900px" }}
    >
      <h2 className="mb-6 text-2xl font-bold text-foreground">
        Page-Level Findings
      </h2>
      <div className="space-y-4">
        {pages.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border bg-muted/30 p-6 text-sm text-muted-foreground">
            No page diagnostics yet. Once crawling finishes, detailed findings
            will appear here.
          </div>
        ) : (
          visiblePages.map((page: any) => {
            const issues = [];
            if (page.audit_data?.structure?.h1_check?.status !== "pass") {
              issues.push({
                severity: "critical",
                msg: "Missing or multiple H1",
              });
            }
            if (
              !page.audit_data?.schema?.schema_presence?.status ||
              page.audit_data?.schema?.schema_presence?.status !== "present"
            ) {
              issues.push({
                severity: "high",
                msg: "Missing schema markup",
              });
            }
            if (page.audit_data?.eeat?.author_presence?.status !== "pass") {
              issues.push({
                severity: "high",
                msg: "Author not identified",
              });
            }
            if (page.audit_data?.structure?.semantic_html?.score_percent < 50) {
              issues.push({
                severity: "medium",
                msg: "Low semantic HTML score",
              });
            }

            return (
              <div
                key={page.id}
                className="rounded-2xl border border-border bg-muted/20 p-6 transition-colors"
              >
                <div className="mb-4 flex flex-col items-start justify-between gap-4 md:flex-row">
                  <div className="min-w-0 flex-1">
                    <h3 className="truncate text-lg font-semibold text-foreground">
                      {page.url}
                    </h3>
                    <p className="truncate text-sm text-muted-foreground">
                      {page.path}
                    </p>
                  </div>
                  <div className="flex-shrink-0 text-right">
                    <div className="text-3xl font-bold text-foreground">
                      {page.overall_score?.toFixed(1) || 0}
                    </div>
                    <div className="text-xs uppercase tracking-wider text-muted-foreground">
                      Score
                    </div>
                  </div>
                </div>

                <div className="mb-4 grid grid-cols-2 gap-4 md:grid-cols-4">
                  <div className="rounded-xl border border-border bg-muted/50 p-3">
                    <div className="mb-1 text-xs text-muted-foreground">H1</div>
                    <div className="font-semibold text-foreground">
                      {page.h1_score?.toFixed(0) || 0}
                    </div>
                  </div>
                  <div className="rounded-xl border border-border bg-muted/50 p-3">
                    <div className="mb-1 text-xs text-muted-foreground">
                      Structure
                    </div>
                    <div className="font-semibold text-foreground">
                      {page.structure_score?.toFixed(0) || 0}
                    </div>
                  </div>
                  <div className="rounded-xl border border-border bg-muted/50 p-3">
                    <div className="mb-1 text-xs text-muted-foreground">
                      Content
                    </div>
                    <div className="font-semibold text-foreground">
                      {page.content_score?.toFixed(0) || 0}
                    </div>
                  </div>
                  <div className="rounded-xl border border-border bg-muted/50 p-3">
                    <div className="mb-1 text-xs text-muted-foreground">
                      E-E-A-T
                    </div>
                    <div className="font-semibold text-foreground">
                      {page.eeat_score?.toFixed(0) || 0}
                    </div>
                  </div>
                </div>

                {issues.length > 0 && (
                  <div className="space-y-2">
                    {issues.map((issue) => (
                      <div
                        key={`${issue.severity}-${issue.msg}`}
                        className={`flex items-center gap-2 rounded-xl border p-3 text-sm ${
                          issue.severity === "critical"
                            ? "border-red-500/20 bg-red-500/10 text-red-600"
                            : issue.severity === "high"
                              ? "border-orange-500/20 bg-orange-500/10 text-orange-600"
                              : "border-amber-500/20 bg-amber-500/10 text-amber-600"
                        }`}
                      >
                        <AlertTriangle className="h-4 w-4 flex-shrink-0" />
                        {issue.msg}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
      {remainingCount > 0 && (
        <div className="mt-6 flex justify-center">
          <Button variant="outline" onClick={onLoadAll}>
            Load {remainingCount} More Page Findings
          </Button>
        </div>
      )}
    </div>
  );
}
