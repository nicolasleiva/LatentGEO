import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import HomePage from "@/app/[locale]/page";
import { usePathname, useRouter } from "next/navigation";
import { useUser } from "@auth0/nextjs-auth0/client";
import { fetchWithBackendAuth } from "@/lib/backend-auth";

jest.mock("next/navigation", () => ({
  useRouter: jest.fn(),
  usePathname: jest.fn(),
}));

jest.mock("@auth0/nextjs-auth0/client", () => ({
  useUser: jest.fn(),
}));

jest.mock("@/lib/api", () => ({
  API_URL: "http://localhost:8000",
}));

jest.mock("@/lib/backend-auth", () => ({
  fetchWithBackendAuth: jest.fn(),
}));

jest.mock("@/components/header", () => ({
  Header: () => <div data-testid="header">Header</div>,
}));

const mockPush = jest.fn();

describe("HomePage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockPush.mockReset();
    window.sessionStorage.clear();
    (useRouter as jest.Mock).mockReturnValue({ push: mockPush });
    (usePathname as jest.Mock).mockReturnValue("/en");
    (useUser as jest.Mock).mockReturnValue({ user: null, isLoading: false });
    (fetchWithBackendAuth as jest.Mock).mockResolvedValue({
      ok: true,
      status: 200,
      statusText: "OK",
      json: async () => [],
      text: async () => "",
      headers: new Headers(),
    });
  });

  it("renders hero copy and core actions for growth positioning", () => {
    render(<HomePage />);

    expect(
      screen.getByRole("heading", {
        name: /make your products discoverable in ai answers/i,
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/turn product pages into ai-citable sources/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/from url -> prioritized fixes -> github prs \+ tests/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/built for chatgpt, perplexity & generative search/i),
    ).toBeInTheDocument();

    expect(
      screen.getByPlaceholderText(/paste your website url/i),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /start free audit/i }),
    ).toBeInTheDocument();
  });

  it("renders proof chips and avoids legacy keyword-heavy headline copy", () => {
    render(<HomePage />);

    expect(
      screen.getByText(/rank products in ai answers/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/get cited as a trusted source/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/turn citations into qualified clicks and sales/i),
    ).toBeInTheDocument();

    expect(screen.queryByText(/keyword discovery/i)).not.toBeInTheDocument();
  });

  it("shows validation feedback for an invalid URL", async () => {
    const user = userEvent.setup();
    render(<HomePage />);

    await user.type(
      screen.getByPlaceholderText(/paste your website url/i),
      "not-a-url",
    );
    await user.click(screen.getByRole("button", { name: /start free audit/i }));

    expect(
      await screen.findByText(/please enter a valid domain or url/i),
    ).toBeInTheDocument();
  });

  it("accepts a domain without protocol and normalizes it to https", async () => {
    const user = userEvent.setup();
    (useUser as jest.Mock).mockReturnValue({
      user: { sub: "auth0|user-456", email: "test@example.com" },
      isLoading: false,
    });
    (fetchWithBackendAuth as jest.Mock)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        statusText: "OK",
        json: async () => [],
        text: async () => "",
        headers: new Headers(),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 202,
        statusText: "Accepted",
        json: async () => ({ id: 99 }),
        text: async () => "",
        headers: new Headers(),
      });

    render(<HomePage />);

    await user.type(
      screen.getByPlaceholderText(/paste your website url/i),
      "ceibo.digital",
    );
    await user.click(screen.getByRole("button", { name: /start free audit/i }));

    await waitFor(() => {
      expect(fetchWithBackendAuth).toHaveBeenCalledWith(
        "http://localhost:8000/api/audits/",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ url: "https://ceibo.digital" }),
        }),
      );
    });
    expect(mockPush).toHaveBeenCalledWith("/en/audits/99");
  });

  it("loads recent audits for authenticated users", async () => {
    (useUser as jest.Mock).mockReturnValue({
      user: { sub: "auth0|user-123", email: "test@example.com" },
      isLoading: false,
    });
    (fetchWithBackendAuth as jest.Mock).mockResolvedValue({
      ok: true,
      status: 200,
      statusText: "OK",
      json: async () => [
        {
          id: 42,
          url: "https://example.com",
          domain: "example.com",
          status: "completed",
          created_at: "2026-02-10T12:00:00Z",
          geo_score: 81,
        },
      ],
      text: async () => "",
      headers: new Headers(),
    });

    render(<HomePage />);

    await waitFor(() => {
      expect(fetchWithBackendAuth).toHaveBeenCalledWith(
        "http://localhost:8000/api/audits",
      );
    });
    expect(await screen.findByText(/^example\.com$/i)).toBeInTheDocument();
  });
});
