export type PdfDownloadUrlPayload = {
  download_url: string;
  expires_in_seconds?: number;
  storage_provider?: string;
};

const FALLBACK_CONTENT_DISPOSITION_NAME = /filename\*=UTF-8''([^;]+)|filename="?([^"]+)"?/i;

export const getPdfDownloadUrlFromPayload = (payload: unknown): string => {
  if (!payload || typeof payload !== "object") {
    throw new Error("Download URL payload is invalid.");
  }

  const candidate = (payload as { download_url?: unknown }).download_url;
  if (typeof candidate !== "string" || !candidate.trim()) {
    throw new Error("Download URL is missing.");
  }

  const downloadUrl = candidate.trim();
  if (
    !downloadUrl.startsWith("https://") &&
    !downloadUrl.startsWith("http://")
  ) {
    throw new Error("Download URL must be absolute.");
  }

  return downloadUrl;
};

export const triggerFileDownload = (
  downloadUrl: string,
  fileName?: string,
): void => {
  const resolvedUrl =
    typeof window !== "undefined"
      ? new URL(downloadUrl, window.location.origin)
      : null;

  const link = document.createElement("a");
  link.href = resolvedUrl ? resolvedUrl.toString() : downloadUrl;
  if (fileName) {
    link.download = fileName;
  }
  link.rel = "noopener";
  document.body.appendChild(link);
  link.click();
  window.setTimeout(() => {
    link.remove();
  }, 0);
};

const extractDownloadFileName = (
  disposition: string | null,
  fallbackFileName: string,
): string => {
  if (!disposition) {
    return fallbackFileName;
  }

  const match = disposition.match(FALLBACK_CONTENT_DISPOSITION_NAME);
  const encodedFileName = match?.[1];
  const plainFileName = match?.[2];
  const candidate = encodedFileName
    ? decodeURIComponent(encodedFileName)
    : plainFileName;

  return candidate?.trim() || fallbackFileName;
};

const readDownloadErrorMessage = async (
  response: Response,
  fallback: string,
): Promise<string> => {
  try {
    const payload: unknown = await response.json();
    if (payload && typeof payload === "object") {
      const error = (payload as { error?: unknown }).error;
      if (typeof error === "string" && error.trim()) {
        return error;
      }
      const detail = (payload as { detail?: unknown }).detail;
      if (typeof detail === "string" && detail.trim()) {
        return detail;
      }
    }
  } catch {
    try {
      const text = await response.text();
      if (text.trim()) {
        return text.trim();
      }
    } catch {
      // Ignore and fall through to the default message.
    }
  }

  return fallback;
};

export const downloadAuditPdf = async (
  auditId: number | string,
): Promise<void> => {
  if (typeof window === "undefined") {
    throw new Error("PDF download is only available in the browser.");
  }

  const normalizedAuditId = Number(auditId);
  if (!Number.isFinite(normalizedAuditId) || normalizedAuditId <= 0) {
    throw new Error("Audit ID is invalid.");
  }

  const response = await fetch(`/api/audits/${normalizedAuditId}/download-pdf`, {
    method: "GET",
    cache: "no-store",
    credentials: "same-origin",
  });

  if (!response.ok) {
    throw new Error(
      await readDownloadErrorMessage(response, "Failed to download PDF."),
    );
  }

  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  const fileName = extractDownloadFileName(
    response.headers.get("content-disposition"),
    `audit_${normalizedAuditId}_report.pdf`,
  );

  try {
    triggerFileDownload(objectUrl, fileName);
  } finally {
    window.setTimeout(() => {
      URL.revokeObjectURL(objectUrl);
    }, 0);
  }
};
