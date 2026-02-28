import { render, screen, waitFor } from "@testing-library/react";
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

const dashboardPayload = {
  audit_id: 3,
  citation_tracking: {
    citation_rate: 0,
    total_queries: 0,
    mentions: 0,
    sentiment_breakdown: {},
  },
  top_opportunities: [],
  competitor_benchmark: {
    has_data: false,
    your_mentions: 0,
  },
};

describe("GEO dashboard page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    (useParams as jest.Mock).mockReturnValue({ id: "3" });
    (usePathname as jest.Mock).mockReturnValue("/en/audits/3/geo");
    (useRouter as jest.Mock).mockReturnValue({ replace: mockReplace });
    (useSearchParams as jest.Mock).mockReturnValue({
      get: (key: string) => (key === "tab" ? "article-engine" : null),
      toString: () => "tab=article-engine",
    });
    (fetchWithBackendAuth as jest.Mock).mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => dashboardPayload,
    });
  });

  it("fetches /api/v1/geo/dashboard only once per load (no loop)", async () => {
    render(<GEODashboardPage />);

    await waitFor(() => {
      expect(fetchWithBackendAuth).toHaveBeenCalledTimes(1);
    });

    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(fetchWithBackendAuth).toHaveBeenCalledTimes(1);
    expect(fetchWithBackendAuth).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/geo/dashboard/3",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it("resolves ?tab=article-engine without crashing and renders the section", async () => {
    render(<GEODashboardPage />);

    await waitFor(() => {
      expect(
        screen.getByRole("heading", {
          name: "Article Engine",
        }),
      ).toBeInTheDocument();
    });
    expect(
      screen.getByText(
        /generate audit-grounded article batches focused on citation and conversion outcomes/i,
      ),
    ).toBeInTheDocument();
  });
});


