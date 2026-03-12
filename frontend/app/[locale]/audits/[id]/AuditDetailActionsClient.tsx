"use client";

import { useMemo } from "react";
import { Download, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { usePdfGeneration } from "@/hooks/usePdfGeneration";
import { usePageSpeedGeneration } from "@/hooks/usePageSpeedGeneration";
import { downloadAuditPdf } from "@/lib/pdf-download";

type AuditDetailActionsClientProps = {
  auditId: string;
  hasPageSpeed: boolean;
};

const getPdfButtonLabel = (status: string, isBusy: boolean): string => {
  if (status === "queued") return "Queued for PDF";
  if (status === "waiting") return "Waiting on PageSpeed";
  if (status === "running" || isBusy) return "Building PDF...";
  if (status === "completed") return "Download PDF";
  if (status === "failed") return "Retry PDF";
  return "Export PDF";
};

export default function AuditDetailActionsClient({
  auditId,
  hasPageSpeed,
}: AuditDetailActionsClientProps) {
  const { state, generate, isBusy } = usePdfGeneration({
    auditId,
    autoDownload: true,
  });
  const {
    state: pageSpeedState,
    generate: generatePageSpeed,
    isBusy: pageSpeedBusy,
  } = usePageSpeedGeneration({
    auditId,
  });
  const [latestWarning] = state.warnings;
  const pdfNotice = useMemo(() => {
    if (state.status === "queued") {
      return "PDF generation queued. Status updates continue in the background until the file is ready.";
    }
    if (state.status === "waiting" && state.waiting_on === "pagespeed") {
      return "PDF queued and waiting for the active PageSpeed pipeline to finish.";
    }
    if (state.status === "running") {
      return "PDF generation in progress.";
    }
    if (state.status === "completed" && state.download_ready) {
      return "PDF ready to download.";
    }
    if (state.status === "failed") {
      return state.error?.message || "PDF generation failed.";
    }
    return null;
  }, [state]);

  const handleGeneratePdf = async () => {
    try {
      if (state.status === "completed" && state.download_ready) {
        await downloadAuditPdf(auditId);
        return;
      }
      await generate();
    } catch (error) {
      window.alert(
        `Error with PDF: ${
          error instanceof Error ? error.message : "Unknown error"
        }`,
      );
    }
  };

  const handleGeneratePageSpeed = async () => {
    try {
      await generatePageSpeed();
    } catch (error) {
      window.alert(
        `Error running PageSpeed: ${
          error instanceof Error ? error.message : "Unknown error"
        }`,
      );
    }
  };

  const pageSpeedNotice = useMemo(() => {
    if (pageSpeedState.status === "queued") {
      return "PageSpeed queued. It will keep running in the background while you move through the audit.";
    }
    if (pageSpeedState.status === "running") {
      return "PageSpeed analysis in progress.";
    }
    if (
      pageSpeedState.status === "completed" &&
      pageSpeedState.pagespeed_available
    ) {
      return hasPageSpeed ? "PageSpeed refreshed." : "PageSpeed data ready.";
    }
    if (pageSpeedState.status === "failed") {
      return (
        pageSpeedState.error?.message ||
        pageSpeedState.warnings[0] ||
        "PageSpeed analysis failed."
      );
    }
    return null;
  }, [hasPageSpeed, pageSpeedState]);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-3">
        <Button
          onClick={handleGeneratePageSpeed}
          disabled={pageSpeedBusy}
          className="glass-button px-6"
        >
          <RefreshCw
            className={`mr-2 h-4 w-4 ${pageSpeedBusy ? "animate-spin" : ""}`}
          />
          {pageSpeedState.status === "queued"
            ? "Queued PageSpeed"
            : pageSpeedBusy || pageSpeedState.status === "running"
              ? "Running PageSpeed"
              : hasPageSpeed || pageSpeedState.pagespeed_available
                ? "Refresh PageSpeed"
                : "Run PageSpeed"}
        </Button>
        <Button
          onClick={handleGeneratePdf}
          disabled={isBusy}
          className="glass-button-primary px-6"
        >
          {isBusy ? (
            <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <Download className="mr-2 h-4 w-4" />
          )}
          {getPdfButtonLabel(state.status, isBusy)}
        </Button>
      </div>

      {pdfNotice ? (
        <p
          className={`text-sm ${
            state.status === "failed"
              ? "text-destructive"
              : "text-muted-foreground"
          }`}
        >
          {pdfNotice}
        </p>
      ) : null}

      {latestWarning ? (
        <p className="text-sm text-amber-600">{latestWarning}</p>
      ) : null}

      {pageSpeedNotice ? (
        <p
          className={`text-sm ${
            pageSpeedState.status === "failed"
              ? "text-destructive"
              : pageSpeedState.warnings[0]
                ? "text-amber-600"
                : "text-muted-foreground"
          }`}
        >
          {pageSpeedState.warnings[0] || pageSpeedNotice}
        </p>
      ) : null}
    </div>
  );
}
