import { render, screen, waitFor } from "@testing-library/react";

import AuditDetailPage from "@/app/[locale]/audits/[id]/page";
import { fetchWithBackendAuth } from "@/lib/backend-auth";
import { useParams, useRouter } from "next/navigation";

jest.mock("next/navigation", () => ({
  useParams: jest.fn(),
  useRouter: jest.fn(),
}));

jest.mock("next/dynamic", () => ({
  __esModule: true,
  default: () => {
    const DynamicStub = () => <div data-testid="dynamic-stub" />;
    return DynamicStub;
  },
}));

jest.mock("next/image", () => {
  const MockNextImage = (props: any) => (
    <img {...props} alt={props.alt || ""} />
  );
  MockNextImage.displayName = "MockNextImage";
  return MockNextImage;
});

jest.mock("@/components/header", () => ({
  Header: () => <div data-testid="header">Header</div>,
}));

jest.mock("@/components/ui/dialog", () => ({
  Dialog: ({ children }: any) => <div>{children}</div>,
  DialogContent: ({ children }: any) => <div>{children}</div>,
  DialogTrigger: ({ children }: any) => <div>{children}</div>,
  DialogTitle: ({ children }: any) => <div>{children}</div>,
}));

jest.mock("@/hooks/useAuditSSE", () => ({
  useAuditSSE: jest.fn(),
}));

jest.mock("@/lib/api", () => ({
  API_URL: "http://localhost:8000",
}));

jest.mock("@/lib/backend-auth", () => ({
  fetchWithBackendAuth: jest.fn(),
}));

const mockPush = jest.fn();
const mockPrefetch = jest.fn();

describe("Audit detail GEO tools navigation", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (useParams as jest.Mock).mockReturnValue({ locale: "en", id: "6" });
    (useRouter as jest.Mock).mockReturnValue({
      push: mockPush,
      prefetch: mockPrefetch,
    });
    (fetchWithBackendAuth as jest.Mock).mockImplementation((url: string) => {
      if (url.endsWith("/api/audits/6")) {
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
          }),
        });
      }
      if (url.endsWith("/api/audits/6/pages")) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => [],
        });
      }
      if (url.endsWith("/api/audits/6/competitors")) {
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
    render(<AuditDetailPage />);

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: /seo & geo tools/i }),
      ).toBeInTheDocument();
    });

    const geoDashboard = screen.getByRole("link", { name: /geo dashboard/i });
    const githubAutoFix = screen.getByRole("link", {
      name: /github auto-fix/i,
    });
    const articleEngine = screen.getByRole("link", { name: /article engine/i });

    expect(geoDashboard).toHaveAttribute("href", "/en/audits/6/geo");
    expect(githubAutoFix).toHaveAttribute(
      "href",
      "/en/audits/6/github-auto-fix",
    );
    expect(articleEngine).toHaveAttribute(
      "href",
      "/en/audits/6/geo?tab=article-engine",
    );

    await waitFor(() => {
      expect(mockPrefetch).toHaveBeenCalledWith("/en/audits/6/geo");
      expect(mockPrefetch).toHaveBeenCalledWith("/en/audits/6/github-auto-fix");
      expect(mockPrefetch).toHaveBeenCalledWith(
        "/en/audits/6/geo?tab=commerce",
      );
    });
  });
});
