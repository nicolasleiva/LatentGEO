vi.mock("@/lib/env", () => ({
  resolveApiBaseUrl: () => "http://localhost:8000",
}));

const getAccessTokenMock = vi.fn();

vi.mock("@auth0/nextjs-auth0/client", () => ({
  getAccessToken: (...args: unknown[]) => getAccessTokenMock(...args),
}));

class MockBroadcastChannel {
  static channels = new Map<string, Set<MockBroadcastChannel>>();

  name: string;
  onmessage: ((event: MessageEvent) => void) | null = null;

  constructor(name: string) {
    this.name = name;
    const listeners = MockBroadcastChannel.channels.get(name) ?? new Set();
    listeners.add(this);
    MockBroadcastChannel.channels.set(name, listeners);
  }

  postMessage(data: unknown) {
    const listeners = MockBroadcastChannel.channels.get(this.name) ?? new Set();
    for (const listener of listeners) {
      if (listener === this) continue;
      listener.onmessage?.({ data } as MessageEvent);
    }
  }

  close() {
    const listeners = MockBroadcastChannel.channels.get(this.name);
    if (!listeners) return;
    listeners.delete(this);
    if (listeners.size === 0) {
      MockBroadcastChannel.channels.delete(this.name);
    }
  }
}

describe("backend-auth cross-tab coordination", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
    window.localStorage.clear();
    MockBroadcastChannel.channels.clear();
    process.env.NEXT_PUBLIC_AUTH0_API_AUDIENCE = "https://api.example.com";
    (
      globalThis as unknown as { BroadcastChannel: typeof MockBroadcastChannel }
    ).BroadcastChannel = MockBroadcastChannel;
  });

  afterEach(() => {
    vi.restoreAllMocks();
    window.localStorage.clear();
    MockBroadcastChannel.channels.clear();
  });

  it("uses broadcasted token when another tab holds refresh lock", async () => {
    const fetchMock = vi.fn();
    global.fetch = fetchMock as unknown as typeof fetch;

    window.localStorage.setItem(
      "backend-auth-token-refresh-lock",
      JSON.stringify({
        owner: "other-tab",
        expires_at: Date.now() + 10_000,
      }),
    );

    const { getBackendAccessToken } = await import("@/lib/backend-auth");

    const tokenPromise = getBackendAccessToken();
    const peer = new MockBroadcastChannel("backend-auth-token");
    setTimeout(() => {
      peer.postMessage({
        type: "token_refreshed",
        token: "shared-token",
        expiry: Date.now() + 120_000,
      });
    }, 0);

    await expect(tokenPromise).resolves.toBe("shared-token");
    expect(fetchMock).not.toHaveBeenCalled();

    const lockValue = window.localStorage.getItem(
      "backend-auth-token-refresh-lock",
    );
    expect(lockValue).not.toContain("shared-token");

    peer.close();
  });

  it("preserves request headers while attaching backend authorization", async () => {
    getAccessTokenMock.mockResolvedValue("test-token");

    let sentRequest: Request | null = null;
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        sentRequest =
          input instanceof Request
            ? new Request(input, init)
            : new Request(input.toString(), init);

        return new Response(JSON.stringify({ ok: true }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      },
    );
    global.fetch = fetchMock as unknown as typeof fetch;

    const { fetchWithBackendAuth } = await import("@/lib/backend-auth");

    const request = new Request("http://localhost:8000/api/v1/audits/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url: "https://v0-auditor-geo-landing-page.vercel.app/",
      }),
    });

    const response = await fetchWithBackendAuth(request);

    expect(response.ok).toBe(true);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(sentRequest).not.toBeNull();
    expect(sentRequest?.headers.get("content-type")).toBe("application/json");
    expect(sentRequest?.headers.get("authorization")).toBe("Bearer test-token");
    await expect(sentRequest?.text()).resolves.toBe(
      JSON.stringify({
        url: "https://v0-auditor-geo-landing-page.vercel.app/",
      }),
    );
  });

  it("falls back to the backend token bridge when client access token is unavailable", async () => {
    getAccessTokenMock.mockResolvedValue(null);

    let sentBackendRequest: Request | null = null;
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = input instanceof Request ? input.url : input.toString();

        if (url.includes("/api/auth/backend-token")) {
          return new Response(
            JSON.stringify({
              token: "bridge-token",
              expires_at: Date.now() + 120_000,
            }),
            {
              status: 200,
              headers: { "Content-Type": "application/json" },
            },
          );
        }

        sentBackendRequest =
          input instanceof Request
            ? new Request(input, init)
            : new Request(input.toString(), init);

        return new Response(JSON.stringify({ ok: true }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      },
    );
    global.fetch = fetchMock as unknown as typeof fetch;

    const { fetchWithBackendAuth } = await import("@/lib/backend-auth");

    const response = await fetchWithBackendAuth(
      "http://localhost:8000/api/v1/geo/dashboard/28",
    );

    expect(response.ok).toBe(true);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(sentBackendRequest).not.toBeNull();
    expect(sentBackendRequest?.headers.get("authorization")).toBe(
      "Bearer bridge-token",
    );
  });
});
