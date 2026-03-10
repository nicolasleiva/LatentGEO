import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import LLMVisibilityPageClient from "@/app/[locale]/audits/[id]/llm-visibility/LLMVisibilityPageClient";
import { api } from "@/lib/api-client";

vi.mock("@/components/header", () => ({
  Header: () => <div data-testid="header">Header</div>,
}));

vi.mock("@/lib/api-client", () => ({
  api: {
    checkLLMVisibility: vi.fn(),
  },
}));

describe("LLMVisibilityPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows Kimi detail errors for visibility checks", async () => {
    const user = userEvent.setup();
    (api.checkLLMVisibility as jest.Mock).mockRejectedValue(
      new Error(
        "Kimi provider is not configured. Set NV_API_KEY_ANALYSIS or NVIDIA_API_KEY or NV_API_KEY.",
      ),
    );

    render(
      <LLMVisibilityPageClient
        auditId="1"
        initialResults={[]}
        initialBrandName="example"
      />,
    );

    await user.type(screen.getByPlaceholderText(/acme corp/i), "Example");
    await user.type(
      screen.getByPlaceholderText(/best seo tools, top marketing agencies/i),
      "best ai tools",
    );
    await user.click(screen.getByRole("button", { name: /check visibility/i }));

    expect(
      await screen.findByText(/Kimi provider is not configured/i),
    ).toBeInTheDocument();
    expect(screen.queryByText(/OpenAI\/Gemini/i)).not.toBeInTheDocument();
  });
});
