import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import ArticleEngine from "@/app/[locale]/audits/[id]/geo/components/ArticleEngine";
import { fetchWithBackendAuth } from "@/lib/backend-auth";

vi.mock("@/lib/backend-auth", () => ({
  fetchWithBackendAuth: vi.fn(),
}));

class MockEventSource {
  static instances: MockEventSource[] = [];

  url: string;
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  close = vi.fn();

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }
}

describe("ArticleEngine component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    MockEventSource.instances = [];
    delete (globalThis as { EventSource?: unknown }).EventSource;
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
          pipeline_stage: "completed",
          strategy_source: "generated_auto",
          global_authority_urls: ["https://authority.example.com/global-guide"],
          unmatched_authority_urls: ["https://authority.example.com/unmatched"],
        },
        is_legacy: false,
        can_regenerate: true,
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
            user_authority_urls: [],
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
    expect(screen.getAllByText(/generated automatically/i).length).toBeGreaterThan(
      0,
    );
    expect(
      screen.getByText(/authority\.example\.com\/unmatched/i),
    ).toBeInTheDocument();
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
        "http://localhost:8000/api/v1/geo/article-engine/latest/3",
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

  it("generates a new batch without topics", async () => {
    (fetchWithBackendAuth as jest.Mock)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ has_data: false }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({
          batch_id: 77,
          status: "processing",
          summary: {
            generated_count: 0,
            failed_count: 0,
            pipeline_stage: "titles_ready",
            strategy_source: "generated_auto",
          },
          is_legacy: false,
          can_regenerate: true,
          articles: [
            {
              index: 1,
              title: "Queued title",
              target_keyword: "queued keyword",
              focus_url: "https://store.example.com/",
              generation_status: "queued",
            },
          ],
        }),
      });

    const user = userEvent.setup();
    render(<ArticleEngine auditId={3} backendUrl="http://localhost:8000" />);

    await user.click(
      screen.getByRole("button", { name: /generate article batch/i }),
    );

    const lastCall = (fetchWithBackendAuth as jest.Mock).mock.calls[1];
    expect(lastCall[0]).toBe("http://localhost:8000/api/v1/geo/article-engine/generate");
    const payload = JSON.parse(lastCall[1].body);
    expect(payload.audit_id).toBe(3);
    expect(payload.target_topics).toBeUndefined();
    expect(await screen.findByText(/queued title/i)).toBeInTheDocument();
  });

  it("sends optional topics and global authority links when provided", async () => {
    (fetchWithBackendAuth as jest.Mock)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ has_data: false }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({
          batch_id: 77,
          status: "processing",
          summary: {
            generated_count: 0,
            failed_count: 0,
            pipeline_stage: "titles_ready",
            strategy_source: "generated_from_topics",
          },
          is_legacy: false,
          can_regenerate: true,
          articles: [
            {
              index: 1,
              title: "Queued title",
              target_keyword: "queued keyword",
              focus_url: "https://store.example.com/",
              generation_status: "queued",
              user_authority_urls: [],
            },
          ],
        }),
      });

    const user = userEvent.setup();
    render(<ArticleEngine auditId={3} backendUrl="http://localhost:8000" />);

    await user.type(
      screen.getByLabelText(/target topics \(comma separated\)/i),
      "odoo colombia, sap business one",
    );
    await user.type(
      screen.getByLabelText(/citation links \(optional\)/i),
      "https://authority.example.com/a{enter}https://authority.example.com/b",
    );
    await user.click(
      screen.getByRole("button", { name: /generate article batch/i }),
    );

    const lastCall = (fetchWithBackendAuth as jest.Mock).mock.calls[1];
    expect(JSON.parse(lastCall[1].body)).toMatchObject({
      audit_id: 3,
      target_topics: ["odoo colombia", "sap business one"],
      authority_urls: [
        "https://authority.example.com/a",
        "https://authority.example.com/b",
      ],
    });
  });

  it("disables regeneration for legacy batches", async () => {
    (fetchWithBackendAuth as jest.Mock).mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        has_data: true,
        batch_id: 55,
        status: "completed",
        summary: {
          generated_count: 1,
          failed_count: 0,
        },
        is_legacy: true,
        can_regenerate: false,
        articles: [
          {
            index: 1,
            title: "Legacy article",
            target_keyword: "legacy keyword",
            focus_url: "https://store.example.com/",
            generation_status: "completed",
          },
        ],
      }),
    });

    render(<ArticleEngine auditId={3} backendUrl="http://localhost:8000" />);

    expect(
      await screen.findByText(/generated before the new title-run system/i),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /regenerate article/i }),
    ).toBeDisabled();
  });

  it("hydrates latest full payload after terminal SSE status", async () => {
    (
      globalThis as unknown as { EventSource: typeof MockEventSource }
    ).EventSource = MockEventSource;

    (fetchWithBackendAuth as jest.Mock)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({
          has_data: true,
          batch_id: 41,
          status: "processing",
          summary: {
            generated_count: 0,
            failed_count: 0,
            pipeline_stage: "generating_articles",
            strategy_source: "generated_auto",
          },
          is_legacy: false,
          can_regenerate: true,
          articles: [
            {
              index: 1,
              title: "Queued title",
              target_keyword: "queued keyword",
              focus_url: "https://store.example.com/",
              generation_status: "queued",
            },
          ],
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({
          has_data: true,
          batch_id: 41,
          status: "completed",
          summary: {
            generated_count: 1,
            failed_count: 0,
            pipeline_stage: "completed",
            strategy_source: "generated_auto",
          },
          is_legacy: false,
          can_regenerate: true,
          articles: [
            {
              index: 1,
              title: "Queued title",
              target_keyword: "queued keyword",
              focus_url: "https://store.example.com/",
              generation_status: "completed",
              citation_readiness_score: 100,
              markdown: "# Final article",
              sources: [
                {
                  title: "Authority Guide",
                  url: "https://authority.example.com/guide",
                },
              ],
              keyword_strategy: {
                primary_keyword: "queued keyword",
                secondary_keywords: ["queued keyword guide"],
                search_intent: "informational",
              },
            },
          ],
        }),
      });

    render(<ArticleEngine auditId={3} backendUrl="http://localhost:8000" />);

    await waitFor(() => expect(MockEventSource.instances.length).toBe(1));
    const source = MockEventSource.instances[0];
    expect(source.url).toBe("/api/sse/article-engine/41/progress");

    act(() => {
      source.onmessage?.(
        new MessageEvent("message", {
          data: JSON.stringify({
            batch_id: 41,
            audit_id: 3,
            status: "completed",
            summary: {
              generated_count: 1,
              failed_count: 0,
              pipeline_stage: "completed",
            },
            articles: [
              {
                index: 1,
                title: "Queued title",
                target_keyword: "queued keyword",
                focus_url: "https://store.example.com/",
                generation_status: "completed",
                generation_error: null,
                citation_readiness_score: 100,
                user_authority_urls: [],
              },
            ],
            is_legacy: false,
            can_regenerate: true,
          }),
        }),
      );
    });

    expect(await screen.findByDisplayValue("# Final article")).toBeInTheDocument();
    expect(source.close).toHaveBeenCalled();
    expect(fetchWithBackendAuth).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/geo/article-engine/latest/3",
    );
    expect((fetchWithBackendAuth as jest.Mock).mock.calls).toHaveLength(2);
  });
});
