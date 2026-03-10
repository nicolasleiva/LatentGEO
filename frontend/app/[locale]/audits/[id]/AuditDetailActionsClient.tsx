"use client";

import { useState } from "react";
import { Download, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { API_URL } from "@/lib/api-client";
import { fetchWithBackendAuth } from "@/lib/backend-auth";
import {
  getPdfDownloadUrlFromPayload,
  triggerFileDownload,
} from "@/lib/pdf-download";

type AuditDetailActionsClientProps = {
  auditId: string;
  hasPageSpeed: boolean;
};

export default function AuditDetailActionsClient({
  auditId,
  hasPageSpeed,
}: AuditDetailActionsClientProps) {
  const [pageSpeedLoading, setPageSpeedLoading] = useState(false);
  const [pdfGenerating, setPdfGenerating] = useState(false);

  const fetchPdfDownloadUrl = async () => {
    let lastError: Error | null = null;

    for (let attempt = 0; attempt < 5; attempt += 1) {
      const downloadResponse = await fetchWithBackendAuth(
        `${API_URL}/api/v1/audits/${auditId}/download-pdf-url`,
      );

      if (downloadResponse.ok) {
        const downloadPayload = await downloadResponse.json().catch(() => null);
        return getPdfDownloadUrlFromPayload(downloadPayload);
      }

      const payload = await downloadResponse.json().catch(() => ({}));
      lastError = new Error(
        payload?.detail || "Failed to obtain PDF download URL.",
      );

      if (downloadResponse.status !== 404 && downloadResponse.status !== 503) {
        break;
      }

      await new Promise((resolve) =>
        setTimeout(resolve, Math.min(1000 * (attempt + 1), 3000)),
      );
    }

    throw lastError ?? new Error("Failed to obtain PDF download URL.");
  };

  const analyzePageSpeed = async () => {
    setPageSpeedLoading(true);
    try {
      const response = await fetchWithBackendAuth(
        `${API_URL}/api/v1/audits/${auditId}/pagespeed`,
        {
          method: "POST",
        },
      );
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload?.detail || "Failed to analyze PageSpeed.");
      }
      window.alert(
        hasPageSpeed
          ? "PageSpeed refreshed successfully."
          : "PageSpeed analysis completed successfully.",
      );
    } catch (error) {
      window.alert(
        `Error running PageSpeed: ${
          error instanceof Error ? error.message : "Unknown error"
        }`,
      );
    } finally {
      setPageSpeedLoading(false);
    }
  };

  const generatePdf = async () => {
    if (pdfGenerating) return;
    setPdfGenerating(true);
    try {
      const generateResponse = await fetchWithBackendAuth(
        `${API_URL}/api/v1/audits/${auditId}/generate-pdf`,
        {
          method: "POST",
        },
      );

      if (generateResponse.status === 409) {
        const payload = await generateResponse.json().catch(() => ({}));
        const retryAfter = Number(payload?.retry_after_seconds || 10);
        window.alert(
          `PDF generation already in progress. Retry in ~${retryAfter}s.`,
        );
        return;
      }

      if (!generateResponse.ok) {
        const payload = await generateResponse.json().catch(() => ({}));
        throw new Error(payload?.detail || "Failed to generate PDF.");
      }

      const downloadUrl = await fetchPdfDownloadUrl();
      triggerFileDownload(downloadUrl, `audit_${auditId}_report.pdf`);
    } catch (error) {
      window.alert(
        `Error generating PDF: ${
          error instanceof Error ? error.message : "Unknown error"
        }`,
      );
    } finally {
      setPdfGenerating(false);
    }
  };

  return (
    <div className="flex flex-wrap gap-3">
      <Button
        onClick={analyzePageSpeed}
        disabled={pageSpeedLoading}
        className="glass-button px-6"
      >
        {pageSpeedLoading ? (
          <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
        ) : (
          <RefreshCw className="mr-2 h-4 w-4" />
        )}
        {hasPageSpeed ? "Refresh PageSpeed" : "Run PageSpeed"}
      </Button>
      <Button
        onClick={generatePdf}
        disabled={pdfGenerating}
        className="glass-button-primary px-6"
      >
        {pdfGenerating ? (
          <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
        ) : (
          <Download className="mr-2 h-4 w-4" />
        )}
        {pdfGenerating ? "Building PDF..." : "Export PDF"}
      </Button>
    </div>
  );
}
