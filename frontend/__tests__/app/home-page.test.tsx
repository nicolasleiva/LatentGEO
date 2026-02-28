import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import HomePage from "@/app/[locale]/page";
import { usePathname, useRouter } from "next/navigation";
import { useCombinedProfile, useRequireAppAuth } from "@/lib/app-auth";
import { createAudit, listAudits } from "@/lib/api-client";

vi.mock("next/navigation", () => ({
  useRouter: vi.fn(),
  usePathname: vi.fn(),
}));

vi.mock("@/lib/app-auth", () => ({
  useRequireAppAuth: vi.fn(),
  useCombinedProfile: vi.fn(),
}));

vi.mock("@/lib/api-client", () => ({
  createAudit: vi.fn(),
  listAudits: vi.fn(),
}));

vi.mock("@/components/header", () => ({
  Header: () => <div data-testid="header">Header</div>,
}));

const mockPush = vi.fn();

const renderPage = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <HomePage />
    </QueryClientProvider>,
  );
};

describe("HomePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockPush.mockReset();
    window.sessionStorage.clear();
    (useRouter as jest.Mock).mockReturnValue({ push: mockPush });
    (usePathname as jest.Mock).mockReturnValue("/en");
    (useRequireAppAuth as jest.Mock).mockReturnValue({
      loading: false,
      ready: true,
      supabase_ok: true,
      auth0_ok: true,
    });
    (useCombinedProfile as jest.Mock).mockReturnValue({
      id: "user-1",
      email: "test@example.com",
      name: "Test User",
      picture: null,
    });
    (listAudits as jest.Mock).mockResolvedValue([]);
    (createAudit as jest.Mock).mockResolvedValue({ id: 99 });
  });

  it("renders hero copy and core actions for growth positioning", () => {
    renderPage();

    expect(
      screen.getByRole("heading", {
        name: /own your category in ai answers/i,
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /run one audit, get a prioritized execution map, and move from insight to shipped changes/i,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /from url -> high-impact gaps -> implementation-ready actions/i,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /built for product marketing, seo, and growth engineering teams/i,
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByPlaceholderText(/paste a public page url/i),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /run free audit/i }),
    ).toBeInTheDocument();
  });

  it("renders proof chips and avoids legacy keyword-heavy headline copy", () => {
    renderPage();

    expect(
      screen.getByText(/own category prompts in ai answers/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/convert citations into qualified sessions/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/ship fixes through engineering workflows/i),
    ).toBeInTheDocument();

    expect(screen.queryByText(/keyword discovery/i)).not.toBeInTheDocument();
  });

  it("shows validation feedback for an invalid URL", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.type(
      screen.getByPlaceholderText(/paste a public page url/i),
      "not-a-url",
    );
    await user.click(screen.getByRole("button", { name: /run free audit/i }));

    expect(
      await screen.findByText(/please enter a valid domain or url/i),
    ).toBeInTheDocument();
  });

  it("accepts a domain without protocol and normalizes it to https", async () => {
    const user = userEvent.setup();
    (useCombinedProfile as jest.Mock).mockReturnValue({
      id: "auth0|user-456",
      email: "test@example.com",
      name: "Test User",
      picture: null,
    });

    renderPage();

    await user.type(
      screen.getByPlaceholderText(/paste a public page url/i),
      "ceibo.digital",
    );
    await user.click(screen.getByRole("button", { name: /run free audit/i }));

    await waitFor(() => {
      expect(createAudit).toHaveBeenCalledWith({ url: "https://ceibo.digital" });
    });
    expect(mockPush).toHaveBeenCalledWith("/en/audits/99");
  });

  it("loads recent audits for authenticated users", async () => {
    (useCombinedProfile as jest.Mock).mockReturnValue({
      id: "auth0|user-123",
      email: "test@example.com",
      name: "Test User",
      picture: null,
    });
    (listAudits as jest.Mock).mockResolvedValue([
      {
        id: 42,
        url: "https://example.com",
        domain: "example.com",
        status: "completed",
        created_at: "2026-02-10T12:00:00Z",
        geo_score: 81,
      },
    ]);

    renderPage();

    await waitFor(() => {
      expect(listAudits).toHaveBeenCalled();
    });
    expect(await screen.findByText(/^example\.com$/i)).toBeInTheDocument();
  });
});
