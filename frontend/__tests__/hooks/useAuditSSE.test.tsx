import { act, renderHook, waitFor } from "@testing-library/react";

import { useAuditSSE } from "@/hooks/useAuditSSE";

vi.mock("@/lib/logger", () => ({
  default: {
    log: vi.fn(),
  },
}));

vi.mock("@/lib/backend-auth", () => ({
  fetchWithBackendAuth: vi.fn(),
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

describe("useAuditSSE", () => {
  beforeEach(() => {
    MockEventSource.instances = [];
    (globalThis as unknown as { EventSource: typeof MockEventSource }).EventSource =
      MockEventSource;
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("connects through same-origin SSE proxy without token in URL", async () => {
    const { result, unmount } = renderHook(() => useAuditSSE(123));

    await waitFor(() => expect(MockEventSource.instances.length).toBe(1));
    const source = MockEventSource.instances[0];

    expect(source.url).toBe("/api/sse/audits/123/progress");
    expect(source.url).not.toContain("token=");

    act(() => {
      source.onopen?.(new Event("open"));
    });

    await waitFor(() => expect(result.current.isConnected).toBe(true));

    unmount();
    expect(source.close).toHaveBeenCalled();
  });
});
