import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AIContentPageClient from "@/app/[locale]/audits/[id]/ai-content/AIContentPageClient";
import { api } from "@/lib/api-client";

vi.mock("@/components/header", () => ({
  Header: () => <div data-testid="header">Header</div>,
}));

vi.mock("@/lib/api-client", () => ({
  api: {
    getAIContent: vi.fn(),
    getAudit: vi.fn(),
    generateAIContent: vi.fn(),
  },
}));

describe("AIContentPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows Kimi backend detail errors and not legacy OpenAI/Gemini message", async () => {
    const user = userEvent.setup();
    (api.generateAIContent as jest.Mock).mockRejectedValue(
      new Error(
        "Kimi provider is not configured. Set NV_API_KEY_ANALYSIS or NVIDIA_API_KEY or NV_API_KEY.",
      ),
    );

    render(
      <AIContentPageClient
        auditId="1"
        initialDomain="example.com"
        initialSuggestions={[]}
      />,
    );

    const topicsInput = screen.getByPlaceholderText(/cloud computing, devops/i);
    await user.type(topicsInput, "AI");
    await user.click(
      screen.getByRole("button", { name: /generate strategy/i }),
    );

    expect(
      await screen.findByText(/Kimi provider is not configured/i),
    ).toBeInTheDocument();
    expect(screen.queryByText(/OpenAI\/Gemini/i)).not.toBeInTheDocument();
    await waitFor(() => {
      expect(api.generateAIContent).toHaveBeenCalledWith("1", "example.com", [
        "AI",
      ]);
    });
  });
});
