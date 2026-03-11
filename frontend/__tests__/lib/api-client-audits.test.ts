import { createAudit } from "@/lib/api-client/audits";
import { fetchWithBackendAuth } from "@/lib/backend-auth";

vi.mock("@/lib/backend-auth", () => ({
  fetchWithBackendAuth: vi.fn(),
}));

describe("api-client audits", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("serializes createAudit as an application/json request", async () => {
    let sentRequest: Request | null = null;

    vi.mocked(fetchWithBackendAuth).mockImplementation(async (input, init) => {
      sentRequest =
        input instanceof Request
          ? new Request(input, init)
          : new Request(input.toString(), init);

      return new Response(JSON.stringify({ id: 321 }), {
        status: 202,
        headers: { "Content-Type": "application/json" },
      });
    });

    await expect(
      createAudit({ url: "https://example.com" }),
    ).resolves.toEqual({ id: 321 });

    expect(sentRequest).not.toBeNull();
    expect(sentRequest?.url).toBe("http://localhost:8000/api/v1/audits/");
    expect(sentRequest?.method).toBe("POST");
    expect(sentRequest?.headers.get("content-type")).toBe("application/json");
    await expect(sentRequest?.text()).resolves.toBe(
      JSON.stringify({ url: "https://example.com" }),
    );
  });
});
