"use client";

import { FileText, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

type AuditNarrativeTabProps = {
  reportLoading: boolean;
  reportMarkdown: string | null;
  reportMessage: string | null;
  fallbackMessage: string;
  onRefresh: () => void;
};

export default function AuditNarrativeTab({
  reportLoading,
  reportMarkdown,
  reportMessage,
  fallbackMessage,
  onRefresh,
}: AuditNarrativeTabProps) {
  return (
    <div
      className="glass-card p-8"
      style={{ contentVisibility: "auto", containIntrinsicSize: "1px 720px" }}
    >
      <div className="mb-6 flex items-center justify-between gap-4">
        <h2 className="flex items-center gap-3 text-2xl font-bold text-foreground">
          <FileText className="h-6 w-6 text-brand" />
          Narrative Report (Markdown)
        </h2>
        <Button variant="outline" onClick={onRefresh}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Refresh
        </Button>
      </div>

      {reportLoading ? (
        <div className="flex items-center gap-2 text-muted-foreground">
          <RefreshCw className="h-4 w-4 animate-spin" />
          Loading narrative report...
        </div>
      ) : reportMarkdown ? (
        <pre className="max-h-[70vh] overflow-auto rounded-xl border border-border bg-muted/40 p-4 text-sm break-words whitespace-pre-wrap">
          {reportMarkdown}
        </pre>
      ) : (
        <div className="text-muted-foreground">
          {reportMessage || fallbackMessage}
        </div>
      )}
    </div>
  );
}
