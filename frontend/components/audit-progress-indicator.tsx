"use client";

import { Clock, AlertTriangle } from "lucide-react";

interface AuditProgressIndicatorProps {
  progress: number;
  status: string;
  hasTimedOut: boolean;
}

export function AuditProgressIndicator({
  progress,
  status,
  hasTimedOut,
}: AuditProgressIndicatorProps) {
  if (status === "completed") return null;

  const getProgressMessage = () => {
    if (status === "pending" && progress === 0) {
      return "⏳ Configuring audit...";
    }
    if (progress < 33) return "1/3: Analyzing your site";
    if (progress < 66) return "2/3: Analyzing competitors";
    if (progress < 100)
      return "3/3: Generating the AI report (this may take 1–2 minutes)";
    return null;
  };

  return (
    <>
      <div className="mt-8">
        <div className="flex justify-between mb-2 text-sm text-muted-foreground">
          <span className="font-medium flex items-center gap-2">
            <Clock className="w-4 h-4" />
            {getProgressMessage()}
          </span>
          <span className="font-semibold">{progress}%</span>
        </div>
        <div className="w-full bg-muted rounded-full h-2 overflow-hidden">
          <div
            className="bg-brand h-full rounded-full transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {hasTimedOut && (
        <div className="mt-4 p-4 bg-yellow-500/10 border border-yellow-500/30 rounded-xl flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-yellow-500 flex-shrink-0 mt-0.5" />
          <div className="text-sm text-amber-700 dark:text-amber-200">
            <p className="font-medium mb-1">
              This analysis is taking longer than usual
            </p>
            <p className="text-xs text-amber-700/80 dark:text-amber-200/80">
              We will notify you by email once it&apos;s ready.
            </p>
          </div>
        </div>
      )}
    </>
  );
}
