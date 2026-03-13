import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";

import AuditDetailActionsClient from "@/app/[locale]/audits/[id]/AuditDetailActionsClient";
import { __resetAuditArtifactsStoreForTests } from "@/hooks/useAuditArtifacts";

vi.mock("@/lib/api-client", () => ({
  API_URL: "http://localhost:8000",
}));

const fetchWithBackendAuthMock = vi.fn();
vi.mock("@/lib/backend-auth", () => ({
  fetchWithBackendAuth: (...args: unknown[]) =>
    fetchWithBackendAuthMock(...args),
}));

const downloadAuditPdfMock = vi.fn();
vi.mock("@/lib/pdf-download", () => ({
  downloadAuditPdf: (...args: unknown[]) => downloadAuditPdfMock(...args),
}));

describe("AuditDetailActionsClient", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
    (globalThis as unknown as { EventSource?: unknown }).EventSource =
      undefined;
  });

  afterEach(() => {
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
    __resetAuditArtifactsStoreForTests();
  });

  it("queues PDF generation, refreshes status, and auto-downloads when the PDF is ready", async () => {
    let artifactStatusPolls = 0;
    fetchWithBackendAuthMock.mockImplementation(
      (url: string, init?: RequestInit) => {
        if (url.endsWith("/artifacts-status")) {
          artifactStatusPolls += 1;
          if (artifactStatusPolls === 1) {
            return Promise.resolve(
              new Response(
                JSON.stringify({
                  audit_id: 42,
                  pagespeed_status: "completed",
                  pagespeed_job_id: null,
                  pagespeed_available: true,
                  pagespeed_warnings: [],
                  pagespeed_error: null,
                  pagespeed_started_at: null,
                  pagespeed_completed_at: null,
                  pagespeed_retry_after_seconds: 0,
                  pagespeed_message: null,
                  pdf_status: "idle",
                  pdf_job_id: null,
                  pdf_available: false,
                  pdf_report_id: null,
                  pdf_waiting_on: null,
                  pdf_dependency_job_id: null,
                  pdf_warnings: [],
                  pdf_error: null,
                  pdf_started_at: null,
                  pdf_completed_at: null,
                  pdf_retry_after_seconds: 0,
                  pdf_message: null,
                  updated_at: "2026-03-11T13:19:00Z",
                }),
                {
                  status: 200,
                  headers: { "Content-Type": "application/json" },
                },
              ),
            );
          }
          return Promise.resolve(
            new Response(
              JSON.stringify({
                audit_id: 42,
                pagespeed_status: "completed",
                pagespeed_job_id: null,
                pagespeed_available: true,
                pagespeed_warnings: [],
                pagespeed_error: null,
                pagespeed_started_at: null,
                pagespeed_completed_at: null,
                pagespeed_retry_after_seconds: 0,
                pagespeed_message: null,
                pdf_status: "completed",
                pdf_job_id: 7,
                pdf_available: true,
                pdf_report_id: 18,
                pdf_waiting_on: null,
                pdf_dependency_job_id: null,
                pdf_warnings: [
                  "PageSpeed data could not be refreshed in time.",
                ],
                pdf_error: null,
                pdf_started_at: "2026-03-11T13:20:00Z",
                pdf_completed_at: "2026-03-11T13:21:00Z",
                pdf_retry_after_seconds: 0,
                pdf_message: null,
                updated_at: "2026-03-11T13:21:00Z",
              }),
              {
                status: 200,
                headers: { "Content-Type": "application/json" },
              },
            ),
          );
        }

        if (url.endsWith("/generate-pdf") && init?.method === "POST") {
          return Promise.resolve(
            new Response(
              JSON.stringify({
                audit_id: 42,
                job_id: 7,
                status: "queued",
                download_ready: false,
                report_id: null,
                warnings: [],
                error: null,
                started_at: null,
                completed_at: null,
                retry_after_seconds: 1,
                waiting_on: null,
                dependency_job_id: null,
              }),
              {
                status: 202,
                headers: { "Content-Type": "application/json" },
              },
            ),
          );
        }

        throw new Error(`Unexpected request in test: ${url}`);
      },
    );

    render(<AuditDetailActionsClient auditId="42" hasPageSpeed={true} />);

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /export pdf/i }));
    });

    await waitFor(() => {
      expect(fetchWithBackendAuthMock).toHaveBeenCalledWith(
        "http://localhost:8000/api/v1/audits/42/generate-pdf",
        { method: "POST" },
      );
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });

    await waitFor(() => {
      expect(fetchWithBackendAuthMock).toHaveBeenCalledWith(
        "http://localhost:8000/api/v1/audits/42/artifacts-status",
      );
    });

    await waitFor(() => {
      expect(downloadAuditPdfMock).toHaveBeenCalledWith(42);
    });
    expect(screen.getByRole("button", { name: /download pdf/i })).toBeEnabled();

    expect(
      screen.getByText("PageSpeed data could not be refreshed in time."),
    ).toBeInTheDocument();

    expect(fetchWithBackendAuthMock).toHaveBeenCalledTimes(3);
  });

  it("disables the download action while a PDF download is in flight", async () => {
    let resolveDownload: (() => void) | null = null;
    downloadAuditPdfMock.mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          resolveDownload = resolve;
        }),
    );
    fetchWithBackendAuthMock.mockImplementation(
      () =>
        Promise.resolve(
          new Response(
            JSON.stringify({
              audit_id: 42,
              pagespeed_status: "completed",
              pagespeed_job_id: null,
              pagespeed_available: true,
              pagespeed_warnings: [],
              pagespeed_error: null,
              pagespeed_started_at: null,
              pagespeed_completed_at: null,
              pagespeed_retry_after_seconds: 0,
              pagespeed_message: null,
              pdf_status: "completed",
              pdf_job_id: 7,
              pdf_available: true,
              pdf_report_id: 18,
              pdf_waiting_on: null,
              pdf_dependency_job_id: null,
              pdf_warnings: [],
              pdf_error: null,
              pdf_started_at: "2026-03-11T13:20:00Z",
              pdf_completed_at: "2026-03-11T13:21:00Z",
              pdf_retry_after_seconds: 0,
              pdf_message: null,
              updated_at: "2026-03-11T13:21:00Z",
            }),
            {
              status: 200,
              headers: { "Content-Type": "application/json" },
            },
          ),
        ),
    );

    render(<AuditDetailActionsClient auditId="42" hasPageSpeed={true} />);

    const downloadButton = await screen.findByRole("button", {
      name: /download pdf/i,
    });
    await act(async () => {
      fireEvent.click(downloadButton);
    });

    await waitFor(() => {
      expect(downloadAuditPdfMock).toHaveBeenCalledWith("42");
    });
    expect(
      screen.getByRole("button", { name: /downloading pdf/i }),
    ).toBeDisabled();

    await act(async () => {
      resolveDownload?.();
    });

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /download pdf/i })).toBeEnabled();
    });
  });
});
