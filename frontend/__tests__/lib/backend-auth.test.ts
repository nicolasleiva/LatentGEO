vi.mock("@/lib/env", () => ({
  resolveApiBaseUrl: () => "http://localhost:8000",
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
    window.localStorage.clear();
    MockBroadcastChannel.channels.clear();
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
});
