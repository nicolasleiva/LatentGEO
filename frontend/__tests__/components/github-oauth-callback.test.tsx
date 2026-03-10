import { act, render, waitFor } from "@testing-library/react";

import GitHubOAuthCallback from "@/components/github-oauth-callback";
import { fetchWithBackendAuth } from "@/lib/backend-auth";

vi.mock("next/navigation", () => ({
  usePathname: vi.fn(() => "/integrations/github/callback"),
}));

vi.mock("@/lib/api", () => ({
  API_URL: "http://localhost:8000",
}));

vi.mock("@/lib/backend-auth", () => ({
  fetchWithBackendAuth: vi.fn(),
}));

describe("GitHubOAuthCallback", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
    window.history.replaceState(
      {},
      "",
      "/integrations/github/callback?code=oauth-code&state=signed-state",
    );
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("redirects back to the signed return_to path after OAuth completes", async () => {
    const handleRedirect = vi.fn();
    (fetchWithBackendAuth as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({
        status: "success",
        connection_id: "gh-conn-1",
        username: "octocat",
        return_to: "/en/audits/29/github-auto-fix",
      }),
    });

    await act(async () => {
      render(<GitHubOAuthCallback onRedirect={handleRedirect} />);
    });

    await waitFor(() => {
      expect(fetchWithBackendAuth).toHaveBeenCalledWith(
        "http://localhost:8000/api/v1/github/callback",
        expect.objectContaining({
          method: "POST",
        }),
      );
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1200);
    });

    expect(handleRedirect).toHaveBeenCalledWith(
      "/en/audits/29/github-auto-fix",
    );
  });
});
