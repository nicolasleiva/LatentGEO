import { act, renderHook, waitFor } from "@testing-library/react";

import { __resetAuditArtifactsStoreForTests } from "@/hooks/useAuditArtifacts";
import { usePageSpeedGeneration } from "@/hooks/usePageSpeedGeneration";
import { usePdfGeneration } from "@/hooks/usePdfGeneration";

vi.mock("@/lib/api-client", () => ({
  API_URL: "http://localhost:8000",
}));

const fetchWithBackendAuthMock = vi.fn();
vi.mock("@/lib/backend-auth", () => ({
  fetchWithBackendAuth: (...args: unknown[]) => fetchWithBackendAuthMock(...args),
}));

vi.mock("@/lib/pdf-download", () => ({
  triggerFileDownload: vi.fn(),
}));

class MockEventSource {
  static instances: MockEventSource[] = [];

  url: string;
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  close = vi.fn();

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }
}

describe("artifact hook wrappers", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    MockEventSource.instances = [];
    (
      globalThis as unknown as { EventSource: typeof MockEventSource }
    ).EventSource = MockEventSource;
  });

  afterEach(() => {
    __resetAuditArtifactsStoreForTests();
  });

  it("keeps wrapper interfaces stable and shares one artifact stream/bootstrap per audit", async () => {
    fetchWithBackendAuthMock.mockImplementation(() =>
      Promise.resolve(
        new Response(
          JSON.stringify({
            audit_id: 42,
            pagespeed_status: "idle",
            pagespeed_job_id: null,
            pagespeed_available: false,
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
      ),
    );

    const pdfHook = renderHook(() =>
      usePdfGeneration({ auditId: 42, autoDownload: true }),
    );
    const pageSpeedHook = renderHook(() =>
      usePageSpeedGeneration({ auditId: 42 }),
    );

    await waitFor(() =>
      expect(fetchWithBackendAuthMock).toHaveBeenCalledTimes(1),
    );
    await waitFor(() => expect(MockEventSource.instances.length).toBe(1));

    expect(MockEventSource.instances[0].url).toBe("/api/sse/audits/42/artifacts");

    expect(Object.keys(pdfHook.result.current).sort()).toEqual(
      ["generate", "isBusy", "isPolling", "isSubmitting", "refreshStatus", "state"].sort(),
    );
    expect(Object.keys(pageSpeedHook.result.current).sort()).toEqual(
      ["generate", "isBusy", "isPolling", "isSubmitting", "refreshStatus", "state"].sort(),
    );

    act(() => {
      MockEventSource.instances[0].onopen?.(new Event("open"));
      MockEventSource.instances[0].onmessage?.(
        new MessageEvent("message", {
          data: JSON.stringify({
            audit_id: 42,
            pagespeed_status: "running",
            pagespeed_job_id: 9,
            pagespeed_available: false,
            pagespeed_warnings: [],
            pagespeed_error: null,
            pagespeed_started_at: "2026-03-11T13:20:00Z",
            pagespeed_completed_at: null,
            pagespeed_retry_after_seconds: 3,
            pagespeed_message: null,
            pdf_status: "waiting",
            pdf_job_id: 7,
            pdf_available: false,
            pdf_report_id: null,
            pdf_waiting_on: "pagespeed",
            pdf_dependency_job_id: 9,
            pdf_warnings: [],
            pdf_error: null,
            pdf_started_at: null,
            pdf_completed_at: null,
            pdf_retry_after_seconds: 3,
            pdf_message: null,
            updated_at: "2026-03-11T13:20:00Z",
          }),
        }),
      );
    });

    await waitFor(() =>
      expect(pdfHook.result.current.state.status).toBe("waiting"),
    );
    expect(pdfHook.result.current.state.waiting_on).toBe("pagespeed");
    expect(pageSpeedHook.result.current.state.status).toBe("running");
    expect(pageSpeedHook.result.current.state.job_id).toBe(9);
  });
});
