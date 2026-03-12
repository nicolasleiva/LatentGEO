import { NextRequest } from "next/server";

const getSessionMock = vi.fn();
const getAccessTokenMock = vi.fn();

vi.mock("@/lib/auth0", () => ({
  auth0: {
    getSession: (...args: unknown[]) => getSessionMock(...args),
    getAccessToken: (...args: unknown[]) => getAccessTokenMock(...args),
  },
}));

vi.mock("@/lib/env", () => ({
  resolveApiBaseUrl: () => "https://backend.example.com",
}));

describe("server SSE proxy", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.resetModules();
    getSessionMock.mockResolvedValue({ user: { sub: "auth0|user-1" } });
    getAccessTokenMock.mockResolvedValue({ token: "backend-token" });
    process.env.AUTH0_API_AUDIENCE = "https://api.example.com";
    process.env.AUTH0_API_SCOPES = "read:app";
  });

  it("keeps abort forwarding active after returning the proxied response", async () => {
    const { proxyProtectedSse } = await import("@/lib/server-sse-proxy");
    const upstreamSignals: AbortSignal[] = [];
    vi.spyOn(globalThis, "fetch").mockImplementation((_url, init) => {
      upstreamSignals.push(init?.signal as AbortSignal);
      return Promise.resolve(
        new Response(new ReadableStream(), {
          status: 200,
          headers: { "Content-Type": "text/event-stream" },
        }),
      );
    });

    const abortController = new AbortController();
    const request = new NextRequest("https://app.example.com/api/sse/test", {
      signal: abortController.signal,
    });

    const response = await proxyProtectedSse(request, "/api/v1/sse/audits/42/progress");

    expect(response.status).toBe(200);
    expect(upstreamSignals).toHaveLength(1);
    expect(upstreamSignals[0].aborted).toBe(false);

    abortController.abort();

    expect(upstreamSignals[0].aborted).toBe(true);
  });
});
