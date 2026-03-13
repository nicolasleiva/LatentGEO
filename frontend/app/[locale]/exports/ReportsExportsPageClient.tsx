"use client";

import { useState } from "react";
import Link from "next/link";
import { Header } from "@/components/header";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { API_URL } from "@/lib/api-client";
import { fetchWithBackendAuth } from "@/lib/backend-auth";
import { formatStableDateTime } from "@/lib/dates";
import { usePdfGeneration } from "@/hooks/usePdfGeneration";
import { downloadAuditPdf } from "@/lib/pdf-download";
import {
  Loader2,
  FileText,
  Download,
  Eye,
  FileJson,
  CheckCircle,
  Clock,
  AlertCircle,
  ArrowLeft,
} from "lucide-react";

export interface ExportAudit {
  id: number;
  url: string;
  domain: string;
  status: string;
  created_at: string;
  completed_at?: string;
}

type ReportsExportsPageClientProps = {
  locale: string;
  initialAudits: ExportAudit[];
};

const getStatusIcon = (status: string) => {
  switch (status) {
    case "completed":
      return <CheckCircle className="h-4 w-4 text-green-400" />;
    case "processing":
    case "running":
      return <Clock className="h-4 w-4 text-yellow-400 animate-pulse" />;
    default:
      return <AlertCircle className="h-4 w-4 text-red-400" />;
  }
};

function ExportAuditRow({
  audit,
  locale,
  onViewMarkdown,
  onDownloadJson,
  markdownLoading,
}: {
  audit: ExportAudit;
  locale: string;
  onViewMarkdown: (auditId: number) => void;
  onDownloadJson: (auditId: number) => void;
  markdownLoading: boolean;
}) {
  const { state, generate, isBusy } = usePdfGeneration({
    auditId: audit.id,
    autoDownload: true,
  });
  const [isDownloadingPdf, setIsDownloadingPdf] = useState(false);

  const handleGeneratePdf = async () => {
    try {
      if (state.status === "completed" && state.download_ready) {
        setIsDownloadingPdf(true);
        try {
          await downloadAuditPdf(audit.id);
        } finally {
          setIsDownloadingPdf(false);
        }
        return;
      }
      const nextState = await generate();
      if (nextState.status === "failed") {
        throw new Error(nextState.error?.message || "PDF generation failed.");
      }
    } catch (error) {
      console.error("Error handling PDF action:", error);
      alert(
        error instanceof Error
          ? error.message
          : "Error handling PDF. Please try again.",
      );
    }
  };

  const pdfStatusMessage =
    state.warnings[0] ||
    (state.status === "queued"
      ? "PDF queued."
      : state.status === "waiting"
        ? "PDF waiting for the active PageSpeed refresh."
        : state.status === "running"
          ? "PDF building..."
          : state.status === "completed" && state.download_ready
            ? "PDF ready to download."
            : state.status === "failed"
              ? state.error?.message || "PDF generation failed."
              : null);

  return (
    <Card className="glass-card p-6 hover:bg-muted/50 transition-all">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-2">
            {getStatusIcon(audit.status)}
            <h2 className="text-lg font-semibold text-foreground">
              {audit.domain}
            </h2>
            <Badge
              variant="outline"
              className="text-xs border-border/70 bg-muted/40 text-muted-foreground"
            >
              #{audit.id}
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground mb-1">{audit.url}</p>
          <p className="text-xs text-muted-foreground/80">
            Completed:{" "}
            {audit.completed_at
              ? formatStableDateTime(audit.completed_at, {
                  fallback: "N/A",
                })
              : "N/A"}
          </p>
          {pdfStatusMessage ? (
            <p
              className={`mt-2 text-xs ${
                state.status === "failed"
                  ? "text-destructive"
                  : state.warnings[0]
                    ? "text-amber-600"
                    : "text-muted-foreground"
              }`}
            >
              {pdfStatusMessage}
            </p>
          ) : null}
        </div>

        <div className="flex gap-2">
          <Button
            onClick={handleGeneratePdf}
            disabled={isBusy || isDownloadingPdf}
            className="glass-button-primary"
            size="sm"
          >
            {isBusy || isDownloadingPdf ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <FileText className="h-4 w-4 mr-2" />
            )}
            {state.status === "queued"
              ? "Queued PDF"
              : state.status === "waiting"
                ? "Waiting on PageSpeed"
                : isDownloadingPdf
                  ? "Downloading PDF"
                  : isBusy || state.status === "running"
                  ? "Building PDF"
                  : state.status === "completed"
                    ? "Download PDF"
                    : state.status === "failed"
                      ? "Retry PDF"
                      : "Build PDF"}
          </Button>

          <Button
            onClick={() => onViewMarkdown(audit.id)}
            disabled={markdownLoading}
            variant="outline"
            className="border-border/70 bg-muted/40 hover:bg-muted/60 text-foreground"
            size="sm"
          >
            <Eye className="h-4 w-4 mr-2" />
            Open Markdown
          </Button>

          <Button
            onClick={() => onDownloadJson(audit.id)}
            variant="outline"
            className="border-border/70 bg-muted/40 hover:bg-muted/60 text-foreground"
            size="sm"
          >
            <FileJson className="h-4 w-4 mr-2" />
            Export JSON
          </Button>

          <Button
            asChild
            variant="ghost"
            className="text-muted-foreground hover:text-foreground hover:bg-muted/50"
            size="sm"
          >
            <Link href={`/${locale}/audits/${audit.id}`}>Open Audit →</Link>
          </Button>
        </div>
      </div>
    </Card>
  );
}

export default function ReportsExportsPageClient({
  locale,
  initialAudits,
}: ReportsExportsPageClientProps) {
  const [selectedAudit, setSelectedAudit] = useState<number | null>(null);
  const [markdownContent, setMarkdownContent] = useState("");
  const [loadingMarkdownAuditId, setLoadingMarkdownAuditId] = useState<
    number | null
  >(null);

  const handleViewMarkdown = async (auditId: number) => {
    if (loadingMarkdownAuditId !== null) {
      return;
    }
    setLoadingMarkdownAuditId(auditId);
    try {
      const response = await fetchWithBackendAuth(
        `${API_URL}/api/v1/reports/markdown/${auditId}`,
      );
      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }
      const result = await response.json();
      setMarkdownContent(result.markdown);
      setSelectedAudit(auditId);
    } catch (error) {
      console.error("Error loading markdown:", error);
      alert("Error loading markdown report");
    } finally {
      setLoadingMarkdownAuditId(null);
    }
  };

  const handleDownloadJSON = async (auditId: number) => {
    try {
      const response = await fetchWithBackendAuth(
        `${API_URL}/api/v1/reports/json/${auditId}`,
      );
      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }
      const data = await response.json();
      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `audit-${auditId}-report.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error("Error downloading JSON:", error);
      alert("Error downloading JSON report");
    }
  };

  if (markdownContent) {
    return (
      <div className="min-h-screen p-6">
        <div className="max-w-5xl mx-auto">
          <div className="mb-6 flex items-center justify-between">
            <Button
              variant="ghost"
              onClick={() => {
                setMarkdownContent("");
                setSelectedAudit(null);
              }}
              className="text-muted-foreground hover:text-foreground hover:bg-muted/50"
            >
              <ArrowLeft className="h-4 w-4 mr-2" /> Back to Reporting Studio
            </Button>
            <Button
              onClick={() => {
                const blob = new Blob([markdownContent], {
                  type: "text/markdown",
                });
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = `audit-${selectedAudit}-report.md`;
                a.click();
                URL.revokeObjectURL(url);
              }}
              className="glass-button-primary"
            >
              <Download className="h-4 w-4 mr-2" /> Export Markdown
            </Button>
          </div>
          <Card className="glass-card p-8">
            <pre className="whitespace-pre-wrap text-sm text-foreground font-mono leading-relaxed">
              {markdownContent}
            </pre>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Header />

      <main className="max-w-7xl mx-auto px-6 py-12">
        <div className="mb-8 animate-fade-up">
          <h1 className="text-3xl md:text-4xl font-semibold tracking-tight">
            Reporting Studio
          </h1>
          <p className="text-muted-foreground mt-2 max-w-2xl">
            Generate board-ready exports and structured data packages from
            completed audits.
          </p>
        </div>

        {/* Reports Grid */}
        <div>
          {initialAudits.length === 0 ? (
            <Card className="glass-card p-12 text-center animate-fade-up">
              <FileText className="h-16 w-16 text-muted-foreground/50 mx-auto mb-4" />
              <h2 className="text-xl font-semibold text-foreground mb-2">
                No Completed Audits
              </h2>
              <p className="text-muted-foreground mb-6">
                Finish at least one audit to unlock report generation.
              </p>
              <Button asChild className="glass-button-primary">
                <Link href={`/${locale}`}>Run New Audit</Link>
              </Button>
            </Card>
          ) : (
            <div className="grid gap-6">
              {initialAudits.map((audit) => (
                <ExportAuditRow
                  key={audit.id}
                  audit={audit}
                  locale={locale}
                  onViewMarkdown={handleViewMarkdown}
                  onDownloadJson={handleDownloadJSON}
                  markdownLoading={loadingMarkdownAuditId !== null}
                />
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
