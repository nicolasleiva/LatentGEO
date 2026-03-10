import { fetchWithBackendAuth } from "@/lib/backend-auth";
import { resolveApiBaseUrl } from "@/lib/env";

export const API_URL = resolveApiBaseUrl();

async function buildApiError(res: Response): Promise<Error> {
  let message = `API error: ${res.status}`;
  try {
    const payload: unknown = await res.json();
    if (payload && typeof payload === "object") {
      const detail = (payload as { detail?: unknown }).detail;
      if (typeof detail === "string" && detail.trim()) {
        message = detail;
      } else if (detail && typeof detail === "object") {
        const detailMessage = (detail as { message?: unknown }).message;
        if (typeof detailMessage === "string" && detailMessage.trim()) {
          message = detailMessage;
        }
      } else {
        const payloadMessage = (payload as { message?: unknown }).message;
        if (typeof payloadMessage === "string" && payloadMessage.trim()) {
          message = payloadMessage;
        }
      }
    }
  } catch {
    // Keep fallback message from status code.
  }
  return new Error(message);
}

async function requestJson<T>(input: string, init?: RequestInit): Promise<T> {
  const res = await fetchWithBackendAuth(input, init);
  if (!res.ok) {
    throw await buildApiError(res);
  }
  return res.json() as Promise<T>;
}

function analysisPillar(score: number, feedback: string) {
  return { score, feedback };
}

export const api = {
  async compareKeywords(yourUrl: string, competitorUrl: string): Promise<any> {
    const params = new URLSearchParams({
      your_url: yourUrl,
      competitor_url: competitorUrl,
    });
    return requestJson(
      `${API_URL}/api/v1/content/keywords/compare?${params.toString()}`,
    );
  },

  async analyzeContent(content: string, keyword?: string): Promise<any> {
    const result = await requestJson<any>(
      `${API_URL}/api/v1/geo/analyze-content`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content, keyword }),
      },
    );

    const score = Number(result?.score || 0);
    const recommendations = Array.isArray(result?.recommendations)
      ? result.recommendations
      : [];

    return {
      score,
      summary:
        (typeof result?.geo_readiness === "string" && result.geo_readiness) ||
        "Content analysis completed.",
      pillars: {
        direct_answer: analysisPillar(
          score,
          "Improve direct answers and response clarity.",
        ),
        structure: analysisPillar(
          score,
          "Use headings, lists, and short paragraphs consistently.",
        ),
        authority: analysisPillar(
          score,
          "Add citations, examples, and stronger trust signals.",
        ),
        semantics: analysisPillar(
          score,
          keyword
            ? `Increase topical coverage around ${keyword}.`
            : "Improve semantic coverage and entity richness.",
        ),
      },
      suggestions: recommendations.map((text: string) => ({
        type: "improvement" as const,
        text,
      })),
      missing_entities: [],
    };
  },

  async comparePageSpeed(url: string): Promise<any> {
    const params = new URLSearchParams({ url });
    return requestJson(
      `${API_URL}/api/v1/pagespeed/compare?${params.toString()}`,
    );
  },

  async generateAIContent(
    auditId: string,
    domain: string,
    topics: string[],
  ): Promise<any[]> {
    const params = new URLSearchParams({ domain });
    return requestJson(
      `${API_URL}/api/v1/ai-content/generate/${auditId}?${params.toString()}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(topics),
      },
    );
  },

  async analyzeBacklinks(auditId: string, domain: string): Promise<any[]> {
    const params = new URLSearchParams({ domain });
    return requestJson(
      `${API_URL}/api/v1/backlinks/analyze/${auditId}?${params.toString()}`,
      {
        method: "POST",
      },
    );
  },

  async getKeywords(auditId: string): Promise<any[]> {
    return requestJson(`${API_URL}/api/v1/keywords/${auditId}`);
  },

  async getAudit(auditId: string): Promise<any> {
    return requestJson(`${API_URL}/api/v1/audits/${auditId}`);
  },

  async researchKeywords(
    auditId: string,
    domain: string,
    seedKeywords: string[],
  ): Promise<any[]> {
    const params = new URLSearchParams({ domain });
    return requestJson(
      `${API_URL}/api/v1/keywords/research/${auditId}?${params.toString()}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(seedKeywords),
      },
    );
  },

  async trackRankings(
    auditId: string,
    domain: string,
    keywords: string[],
  ): Promise<any[]> {
    const params = new URLSearchParams({ domain });
    return requestJson(
      `${API_URL}/api/v1/rank-tracking/track/${auditId}?${params.toString()}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(keywords),
      },
    );
  },

  async checkLLMVisibility(
    auditId: string,
    brandName: string,
    queries: string[],
  ): Promise<any[]> {
    const params = new URLSearchParams({ brand_name: brandName });
    return requestJson(
      `${API_URL}/api/v1/llm-visibility/check/${auditId}?${params.toString()}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(queries),
      },
    );
  },
};
