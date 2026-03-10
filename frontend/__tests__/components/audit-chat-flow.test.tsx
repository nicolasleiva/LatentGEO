import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { AuditChatFlow } from "@/components/audit-chat-flow";
import { fetchWithBackendAuth } from "@/lib/backend-auth";

vi.mock("@/lib/api-client", () => ({
  API_URL: "http://localhost:8000",
}));

vi.mock("@/lib/backend-auth", () => ({
  fetchWithBackendAuth: vi.fn(),
}));

describe("AuditChatFlow", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
    HTMLElement.prototype.scrollTo = vi.fn();
    (fetchWithBackendAuth as jest.Mock).mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({}),
      text: async () => "",
    });
  });

  afterEach(() => {
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
  });

  it("keeps the global intake limited to competitors, market, and launch", async () => {
    const onComplete = vi.fn();
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

    render(<AuditChatFlow auditId={42} onComplete={onComplete} />);

    act(() => {
      vi.runAllTimers();
    });

    expect(screen.getByText("Competitors")).toBeInTheDocument();
    expect(screen.getByText("Markets")).toBeInTheDocument();
    expect(screen.getByText("Launch")).toBeInTheDocument();
    expect(screen.queryByText("Articles")).not.toBeInTheDocument();
    expect(screen.queryByText("Commerce")).not.toBeInTheDocument();
    expect(
      screen.getByText(/Two quick questions to personalize your analysis/i),
    ).toBeInTheDocument();

    const input = screen.getByPlaceholderText("Type your response...");
    await user.type(input, "competitor.example.com");
    await user.click(screen.getByRole("button"));

    act(() => {
      vi.runAllTimers();
    });

    await user.type(
      screen.getByPlaceholderText("Type your response..."),
      "LATAM",
    );
    await user.click(screen.getByRole("button"));

    act(() => {
      vi.runAllTimers();
    });

    await waitFor(() => {
      expect(fetchWithBackendAuth).toHaveBeenCalledTimes(1);
      expect(onComplete).toHaveBeenCalledTimes(1);
    });

    const [url, options] = (fetchWithBackendAuth as jest.Mock).mock.calls[0];
    expect(url).toBe("http://localhost:8000/api/v1/audits/chat/config");

    const body = JSON.parse(options.body);
    expect(body).toEqual({
      audit_id: 42,
      language: "en",
      competitors: ["https://competitor.example.com"],
      market: "LATAM",
    });
    expect(body).not.toHaveProperty("add_articles");
    expect(body).not.toHaveProperty("article_count");
    expect(body).not.toHaveProperty("improve_ecommerce_fixes");
  });
});
