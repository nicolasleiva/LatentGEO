import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import AuditDetailPageClient from "@/app/[locale]/audits/[id]/AuditDetailPageClient";
import { fetchWithBackendAuth } from "@/lib/backend-auth";
import { useParams, useRouter } from "next/navigation";

vi.mock("next/navigation", () => ({
  useParams: vi.fn(),
  useRouter: vi.fn(),
}));

vi.mock("next/dynamic", () => ({
  __esModule: true,
  default: () => {
    const DynamicStub = () => <div data-testid="dynamic-stub" />;
    return DynamicStub;
  },
}));

vi.mock("next/image", () => {
  const MockNextImage = (props: any) => (
    <span data-testid="next-image" data-alt={props.alt || ""} />
  );
  MockNextImage.displayName = "MockNextImage";
  return { default: MockNextImage };
});

vi.mock("@/components/header", () => ({
  Header: () => <div data-testid="header">Header</div>,
}));

vi.mock("@/components/ui/dialog", () => ({
  Dialog: ({ children }: any) => <div>{children}</div>,
  DialogContent: ({ children }: any) => <div>{children}</div>,
  DialogTrigger: ({ children }: any) => <div>{children}</div>,
  DialogTitle: ({ children }: any) => <div>{children}</div>,
}));

vi.mock("@/hooks/useAuditSSE", () => ({
  useAuditSSE: vi.fn(),
}));

vi.mock("@/lib/api-client", () => ({
  API_URL: "http://localhost:8000",
}));

vi.mock("@/lib/backend-auth", () => ({
  fetchWithBackendAuth: vi.fn(),
}));

const mockPush = vi.fn();
const mockPrefetch = vi.fn();

describe("Audit detail GEO tools navigation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (useParams as jest.Mock).mockReturnValue({ locale: "en", id: "6" });
    (useRouter as jest.Mock).mockReturnValue({
      push: mockPush,
      prefetch: mockPrefetch,
    });
    (fetchWithBackendAuth as jest.Mock).mockImplementation((url: string) => {
      if (url.endsWith("/api/v1/audits/6")) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            id: 6,
            url: "https://petshop.example.com",
            status: "completed",
            progress: 100,
            created_at: "2026-02-18T00:00:00Z",
            target_audit: {
              schema: { schema_presence: { status: "absent" } },
              structure: {
                h1_check: { status: "warn" },
                semantic_html: { score_percent: 17 },
              },
              content: { conversational_tone: { score: 0 } },
              eeat: { author_presence: { status: "warn" } },
            },
            external_intelligence: { category: "E-commerce" },
            competitor_audits: [],
            intake_profile: {
              add_articles: true,
              article_count: 4,
            },
            runtime_diagnostics: [
              {
                source: "pagespeed",
                stage: "run-pagespeed",
                severity: "error",
                code: "pagespeed_failed",
                message:
                  "PageSpeed analysis failed before performance data could be refreshed.",
              },
            ],
          }),
        });
      }
      if (url.endsWith("/api/v1/audits/6/pages")) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => [],
        });
      }
      if (url.endsWith("/api/v1/audits/6/competitors")) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => [],
        });
      }
      return Promise.resolve({
        ok: false,
        status: 404,
        json: async () => ({}),
      });
    });
  });

  it("renders GEO tool links with locale path and prefetches critical routes", async () => {
    const user = userEvent.setup();
    render(<AuditDetailPageClient />);

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: /execution tool suite/i }),
      ).toBeInTheDocument();
    });
    expect(screen.getByTestId("pipeline-diagnostics")).toBeInTheDocument();

    const geoDashboard = screen.getByRole("link", { name: /geo dashboard/i });
    const githubAutoFix = screen.getByRole("link", {
      name: /github auto-fix/i,
    });
    const articleEngine = screen.getByRole("link", { name: /article engine/i });
    const odooDelivery = screen.getByRole("link", {
      name: /odoo delivery pack/i,
    });

    expect(geoDashboard).toHaveAttribute("href", "/en/audits/6/geo");
    expect(githubAutoFix).toHaveAttribute(
      "href",
      "/en/audits/6/github-auto-fix",
    );
    expect(articleEngine).toHaveAttribute(
      "href",
      "/en/audits/6/geo?tab=article-engine&articleCount=4",
    );
    expect(odooDelivery).toHaveAttribute("href", "/en/audits/6/odoo-delivery");

    await user.hover(geoDashboard);
    await user.hover(githubAutoFix);
    await user.hover(
      screen.getByRole("link", { name: /ecommerce query analyzer/i }),
    );
    await user.hover(odooDelivery);

    expect(mockPrefetch).toHaveBeenCalledWith("/en/audits/6/geo");
    expect(mockPrefetch).toHaveBeenCalledWith("/en/audits/6/github-auto-fix");
    expect(mockPrefetch).toHaveBeenCalledWith("/en/audits/6/geo?tab=commerce");
    expect(mockPrefetch).toHaveBeenCalledWith("/en/audits/6/odoo-delivery");
  });

  it("hydrates the same dashboard from overview shell data after refresh", async () => {
    (fetchWithBackendAuth as jest.Mock).mockImplementation((url: string) => {
      if (url.endsWith("/api/v1/audits/6/pages")) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => [],
        });
      }
      if (url.endsWith("/api/v1/audits/6/competitors")) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => [
            {
              domain: "leader.example.com",
              url: "https://leader.example.com",
              geo_score: 76,
            },
          ],
        });
      }
      return Promise.resolve({
        ok: false,
        status: 404,
        json: async () => ({}),
      });
    });

    render(
      <AuditDetailPageClient
        auditId="6"
        locale="en"
        initialAudit={{
          id: 6,
          url: "https://petshop.example.com",
          status: "completed",
          progress: 100,
          created_at: "2026-02-18T00:00:00Z",
          completed_at: "2026-02-18T00:10:00Z",
          geo_score: 71,
          competitor_count: 2,
          fix_plan_count: 3,
          external_intelligence: { category: "E-commerce" },
          diagnostics_summary: [],
        }}
        initialAuditIsOverview
      />,
    );

    await waitFor(() => {
      expect(fetchWithBackendAuth).not.toHaveBeenCalledWith(
        "http://localhost:8000/api/v1/audits/6",
      );
    });

    await waitFor(() => {
      const executionSignalsCard =
        screen.getByText("Execution Signals").parentElement?.parentElement;

      expect(executionSignalsCard).not.toBeNull();
      const scoped = within(executionSignalsCard as HTMLElement);
      const competitorsRow = scoped
        .getByText("Competitors found")
        .closest("div");
      const fixPlanRow = scoped.getByText("Fix plan items").closest("div");

      expect(competitorsRow).not.toBeNull();
      expect(fixPlanRow).not.toBeNull();
      expect(
        within(competitorsRow as HTMLElement).getByText("2"),
      ).toBeInTheDocument();
      expect(
        within(fixPlanRow as HTMLElement).getByText("3"),
      ).toBeInTheDocument();
    });
  });
});
