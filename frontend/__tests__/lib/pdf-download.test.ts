import { describe, expect, it, vi } from "vitest";

import {
  __resetPdfDownloadStateForTests,
  downloadAuditPdf,
  getPdfDownloadUrlFromPayload,
  triggerFileDownload,
} from "@/lib/pdf-download";

describe("pdf-download helpers", () => {
  afterEach(() => {
    __resetPdfDownloadStateForTests();
    vi.restoreAllMocks();
  });

  it("returns absolute download URL from payload", () => {
    const payload = {
      download_url:
        "https://project.supabase.co/storage/v1/object/sign/audits/3/report.pdf",
      expires_in_seconds: 3600,
      storage_provider: "supabase",
    };

    expect(getPdfDownloadUrlFromPayload(payload)).toBe(payload.download_url);
  });

  it("throws when payload does not include an absolute URL", () => {
    expect(() =>
      getPdfDownloadUrlFromPayload({
        download_url: "/storage/v1/object/sign/x",
      }),
    ).toThrow("Download URL must be absolute.");
  });

  it("creates and clicks a download link", () => {
    const clickSpy = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => {});

    const appendSpy = vi.spyOn(document.body, "appendChild");

    triggerFileDownload("https://files.example.com/report.pdf", "report.pdf");

    expect(clickSpy).toHaveBeenCalledTimes(1);
    expect(appendSpy).toHaveBeenCalledTimes(1);
    const anchor = appendSpy.mock.calls[0][0] as HTMLAnchorElement;
    expect(anchor.download).toBe("report.pdf");
    expect(anchor.href).toBe("https://files.example.com/report.pdf");
  });

  it("downloads audit PDFs through the protected frontend route without navigating the page", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(new Blob(["pdf-data"], { type: "application/pdf" }), {
        status: 200,
        headers: {
          "Content-Type": "application/pdf",
          "Content-Disposition": 'attachment; filename="audit_42_report.pdf"',
        },
      }),
    );
    const clickSpy = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => {});
    const appendSpy = vi.spyOn(document.body, "appendChild");
    const createObjectUrlSpy = vi
      .spyOn(URL, "createObjectURL")
      .mockReturnValue("blob:https://app.test/report");
    const revokeObjectUrlSpy = vi
      .spyOn(URL, "revokeObjectURL")
      .mockImplementation(() => {});

    await downloadAuditPdf(42);

    expect(fetchMock).toHaveBeenCalledWith("/api/audits/42/download-pdf", {
      method: "GET",
      cache: "no-store",
      credentials: "same-origin",
    });
    expect(createObjectUrlSpy).toHaveBeenCalledTimes(1);
    expect(clickSpy).toHaveBeenCalledTimes(1);
    expect(appendSpy).toHaveBeenCalledTimes(1);
    const anchor = appendSpy.mock.calls[0][0] as HTMLAnchorElement;
    expect(anchor.download).toBe("audit_42_report.pdf");
    expect(anchor.href).toBe("blob:https://app.test/report");
    expect(revokeObjectUrlSpy).not.toHaveBeenCalled();
  });

  it("surfaces plain-text download failures even after JSON parsing fails", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("Signed URL expired", {
        status: 502,
        headers: { "Content-Type": "text/plain" },
      }),
    );

    await expect(downloadAuditPdf(42)).rejects.toThrow("Signed URL expired");
  });

  it("deduplicates concurrent downloads for the same audit", async () => {
    let releaseDownload: (() => void) | null = null;
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(
      () =>
        new Promise<Response>((resolve) => {
          releaseDownload = () =>
            resolve(
              new Response(new Blob(["pdf-data"], { type: "application/pdf" }), {
                status: 200,
                headers: {
                  "Content-Type": "application/pdf",
                  "Content-Disposition":
                    'attachment; filename="audit_42_report.pdf"',
                },
              }),
            );
        }),
    );
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    vi.spyOn(document.body, "appendChild");
    vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:https://app.test/report");
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});

    const firstDownload = downloadAuditPdf(42);
    const secondDownload = downloadAuditPdf(42);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    if (!releaseDownload) {
      throw new Error("Expected the download promise to be pending.");
    }
    releaseDownload();
    await Promise.all([firstDownload, secondDownload]);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
