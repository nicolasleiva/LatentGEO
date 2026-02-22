import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import GEODashboardPage from "@/app/[locale]/audits/[id]/geo/page";
import {
  useParams,
  usePathname,
  useRouter,
  useSearchParams,
} from "next/navigation";
import { fetchWithBackendAuth } from "@/lib/backend-auth";

vi.mock("next/navigation", () => ({
  useParams: vi.fn(),
  usePathname: vi.fn(),
  useRouter: vi.fn(),
  useSearchParams: vi.fn(),
}));

vi.mock("next/dynamic", () => ({
  __esModule: true,
  default: () => {
    const DynamicStub = () => <div data-testid="dynamic-stub" />;
    return DynamicStub;
  },
}));

vi.mock("@/components/header", () => ({
  Header: () => <div data-testid="header">Header</div>,
}));

vi.mock("@/lib/api", () => ({
  API_URL: "http://localhost:8000",
}));

vi.mock("@/lib/backend-auth", () => ({
  fetchWithBackendAuth: vi.fn(),
}));

const mockReplace = vi.fn();

describe("GEO tool menu", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (useParams as jest.Mock).mockReturnValue({ id: "3" });
    (usePathname as jest.Mock).mockReturnValue("/en/audits/3/geo");
    (useRouter as jest.Mock).mockReturnValue({ replace: mockReplace });
    (useSearchParams as jest.Mock).mockReturnValue({
      get: () => "opportunities",
      toString: () => "tab=opportunities",
    });
    (fetchWithBackendAuth as jest.Mock).mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        audit_id: 3,
        citation_tracking: {
          citation_rate: 0,
          total_queries: 0,
          mentions: 0,
          sentiment_breakdown: {},
        },
        top_opportunities: [],
        competitor_benchmark: { has_data: false, your_mentions: 0 },
      }),
    });
  });

  it("renders grouped menu and switches tab through selector", async () => {
    const user = userEvent.setup();
    render(<GEODashboardPage />);

    await waitFor(() =>
      expect(screen.getByText("Tool suite")).toBeInTheDocument(),
    );

    const trigger = screen.getByRole("combobox");
    await user.click(trigger);
    await user.click(screen.getByText("Benchmark"));

    expect(mockReplace).toHaveBeenCalledWith(
      "/en/audits/3/geo?tab=competitors",
      { scroll: false },
    );
  });
});

