"use client";

import dynamic from "next/dynamic";
import { useState } from "react";
import { ChevronDown, History } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

const ScoreHistoryChart = dynamic(
  () =>
    import("@/components/score-history-chart").then(
      (mod) => mod.ScoreHistoryChart,
    ),
  {
    ssr: false,
    loading: () => (
      <div className="rounded-2xl border border-dashed border-border/60 bg-muted/20 py-12 text-center text-sm text-muted-foreground">
        Loading history explorer...
      </div>
    ),
  },
);

type AnalyticsHistoryExplorerProps = {
  recentAudits: Array<{ domain?: string }>;
};

export default function AnalyticsHistoryExplorer({
  recentAudits,
}: AnalyticsHistoryExplorerProps) {
  const [selectedDomain, setSelectedDomain] = useState<string>("");
  const [showHistory, setShowHistory] = useState(false);

  return (
    <Card className="glass-card p-6">
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="rounded-lg bg-brand/10 p-2">
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
          <label htmlFor="domain-history-select" className="sr-only">
            Select a domain for historical score tracking
          </label>
          <select
            id="domain-history-select"
            value={selectedDomain}
            onChange={(event) => setSelectedDomain(event.target.value)}
            className="glass-input rounded-lg px-4 py-2 text-sm"
          >
            <option value="">Select domain</option>
            {recentAudits.map((audit) => (
              <option key={audit.domain} value={audit.domain}>
                {audit.domain}
              </option>
            ))}
          </select>

          <Button
            variant="outline"
            onClick={() => setShowHistory((current) => !current)}
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
      ) : showHistory ? (
        <div className="glass-panel rounded-2xl border border-dashed border-border/60 py-12 text-center text-muted-foreground">
          <History className="mx-auto mb-3 h-12 w-12 opacity-40" />
          <p>Select a domain to view its score history.</p>
        </div>
      ) : null}
    </Card>
  );
}
