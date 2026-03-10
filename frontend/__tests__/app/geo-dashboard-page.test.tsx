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

vi.mock("@/lib/api-client", () => ({
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

const competitorSummaryPayload = {
  audit_id: 3,
  total_competitors: 2,
  your_geo_score: 61,
  average_competitor_score: 54,
  position: "Por encima del promedio",
  competitors: [
    {
      domain: "leader.example.com",
      url: "https://leader.example.com",
      geo_score: 68,
    },
    {
      domain: "runnerup.example.com",
      url: "https://runnerup.example.com",
      geo_score: 40,
    },
  ],
  identified_gaps: ["Schema faltante: FAQPage"],
};

const auditedCompetitorsPayload = [
  {
    domain: "leader.example.com",
    url: "https://leader.example.com",
    geo_score: 68,
    schema_present: true,
    structure_score: 74,
    eeat_score: 80,
    h1_present: true,
    tone_score: 7.2,
  },
  {
    domain: "runnerup.example.com",
    url: "https://runnerup.example.com",
    geo_score: 40,
    schema_present: false,
    structure_score: 42,
    eeat_score: 35,
    h1_present: false,
    tone_score: 3.8,
  },
];

describe("GEO dashboard page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    window.history.replaceState({}, "", "/en/audits/3/geo?tab=article-engine");
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

    const articleHeading = await screen.findByRole("heading", {
      name: "Article Engine",
    });
    expect(articleHeading).toBeInTheDocument();
    expect(
      screen.getByText(
        /generate audit-grounded article batches focused on citation and conversion outcomes/i,
      ),
    ).toBeInTheDocument();
  });

  it("renders audited competitor benchmark automatically in the benchmark tab", async () => {
    window.history.replaceState({}, "", "/en/audits/3/geo?tab=competitors");
    (useSearchParams as jest.Mock).mockReturnValue({
      get: (key: string) => (key === "tab" ? "competitors" : null),
      toString: () => "tab=competitors",
    });
    (fetchWithBackendAuth as jest.Mock).mockImplementation((url: string) => {
      if (url.endsWith("/api/v1/geo/dashboard/3")) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => dashboardPayload,
        });
      }
      if (url.endsWith("/api/v1/analytics/competitors/3")) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => competitorSummaryPayload,
        });
      }
      if (url.includes("/api/v1/audits/3/competitors")) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => auditedCompetitorsPayload,
        });
      }
      return Promise.resolve({
        ok: false,
        status: 404,
        json: async () => ({}),
      });
    });

    render(<GEODashboardPage />);

    await screen.findByText("Audited Competitor Ranking");
    expect(screen.getAllByText("leader.example.com").length).toBeGreaterThan(0);
    expect(screen.getByText("Schema faltante: FAQPage")).toBeInTheDocument();
    expect(screen.getByText("Ad Hoc Benchmark")).toBeInTheDocument();

    await waitFor(() => {
      expect(fetchWithBackendAuth).toHaveBeenCalledWith(
        "http://localhost:8000/api/v1/analytics/competitors/3",
      );
    });
  });
});



