import { describe, expect, it, vi } from "vitest";

import {
  getPdfDownloadUrlFromPayload,
  triggerFileDownload,
} from "@/lib/pdf-download";

describe("pdf-download helpers", () => {
  it("returns absolute download URL from payload", () => {
    const payload = {
      download_url: "https://project.supabase.co/storage/v1/object/sign/audits/3/report.pdf",
      expires_in_seconds: 3600,
      storage_provider: "supabase",
    };

    expect(getPdfDownloadUrlFromPayload(payload)).toBe(payload.download_url);
  });

  it("throws when payload does not include an absolute URL", () => {
    expect(() =>
      getPdfDownloadUrlFromPayload({ download_url: "/storage/v1/object/sign/x" }),
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
});
