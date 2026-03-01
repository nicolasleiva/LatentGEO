export type PdfDownloadUrlPayload = {
  download_url: string;
  expires_in_seconds?: number;
  storage_provider?: string;
};

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
  const link = document.createElement("a");
  link.href = downloadUrl;
  if (fileName) {
    link.download = fileName;
  }
  link.rel = "noopener";
  document.body.appendChild(link);
  link.click();
  link.remove();
};
