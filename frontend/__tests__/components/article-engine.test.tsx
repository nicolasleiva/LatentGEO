import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import ArticleEngine from "@/app/[locale]/audits/[id]/geo/components/ArticleEngine";
import { fetchWithBackendAuth } from "@/lib/backend-auth";

jest.mock("@/lib/backend-auth", () => ({
  fetchWithBackendAuth: jest.fn(),
}));

describe("ArticleEngine component", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders keyword strategy and competitor gaps from latest batch", async () => {
    (fetchWithBackendAuth as jest.Mock).mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        has_data: true,
        batch_id: 99,
        status: "completed",
        summary: {
          generated_count: 1,
          failed_count: 0,
          average_citation_readiness_score: 90,
        },
        articles: [
          {
            index: 1,
            title: "AI Strategy Suggested Title",
            target_keyword: "zapatilla nike",
            focus_url: "https://store.example.com/",
            citation_readiness_score: 90,
            generation_status: "completed",
            markdown: "# Article markdown",
            keyword_strategy: {
              primary_keyword: "zapatilla nike",
              secondary_keywords: [
                "comprar zapatilla nike",
                "zapatilla nike ofertas ar",
              ],
              search_intent: "commercial",
            },
            competitor_gap_map: {
              schema: [{ gap: "Missing Product schema" }],
            },
            evidence_summary: [
              {
                claim: "Competitor dominates top result",
                source_url: "https://www.mercadolibre.com.ar/zapatillas-nike",
              },
            ],
            sources: [
              {
                title: "Statista",
                url: "https://www.statista.com/topics/123/footwear/",
              },
            ],
          },
        ],
      }),
    });

    render(<ArticleEngine auditId={3} backendUrl="http://localhost:8000" />);

    expect(await screen.findByText("Keyword Strategy")).toBeInTheDocument();
    expect(screen.getByText(/primary:/i)).toBeInTheDocument();
    expect(screen.getByText(/zapatilla nike ofertas ar/i)).toBeInTheDocument();
    expect(screen.getByText(/missing product schema/i)).toBeInTheDocument();
    expect(screen.getByText(/evidence summary/i)).toBeInTheDocument();
  });

  it("shows explicit backend error when data pack is incomplete", async () => {
    (fetchWithBackendAuth as jest.Mock)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ has_data: false }),
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 422,
        text: async () =>
          JSON.stringify({
            detail: {
              code: "ARTICLE_DATA_PACK_INCOMPLETE",
              message: "ARTICLE_DATA_PACK_INCOMPLETE: missing required fields",
            },
          }),
      });

    const user = userEvent.setup();
    render(<ArticleEngine auditId={3} backendUrl="http://localhost:8000" />);

    await waitFor(() => {
      expect(fetchWithBackendAuth).toHaveBeenCalledWith(
        "http://localhost:8000/api/geo/article-engine/latest/3",
      );
    });

    await user.click(
      screen.getByRole("button", { name: /generate article batch/i }),
    );

    expect(
      await screen.findByText(
        /ARTICLE_DATA_PACK_INCOMPLETE: ARTICLE_DATA_PACK_INCOMPLETE: missing required fields/i,
      ),
    ).toBeInTheDocument();
  });
});
