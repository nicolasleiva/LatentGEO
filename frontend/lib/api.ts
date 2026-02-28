import type { AuditSummary, PageAudit, CompetitorData } from "./types";
import { fetchWithBackendAuth } from "./backend-auth";
import { resolveApiBaseUrl } from "./env";

// DEPRECATED: use "@/lib/api-client/*" for new code.
// This module is kept temporarily to avoid a large flag-day migration.
export const API_URL = resolveApiBaseUrl();

class APIService {
  private baseUrl = API_URL;

  private async buildApiError(res: Response): Promise<Error> {
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

  async searchAI(query: string): Promise<{
    response: string;
    suggestions: string[];
    audit_started?: boolean;
    audit_id?: number;
  }> {
    const res = await fetchWithBackendAuth(`${this.baseUrl}/api/v1/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async createAudit(config: {
    url: string;
    maxPages?: number;
    competitors?: string[];
    user_id?: string;
    user_email?: string;
  }): Promise<AuditSummary> {
    const res = await fetchWithBackendAuth(`${this.baseUrl}/api/v1/audits`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(config),
    });
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async listAudits(userEmail?: string): Promise<any[]> {
    const params = new URLSearchParams();
    if (userEmail) params.set("user_email", userEmail);
    const url = params.toString()
      ? `${this.baseUrl}/api/v1/audits?${params}`
      : `${this.baseUrl}/api/v1/audits`;
    const res = await fetchWithBackendAuth(url);
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    const data = await res.json();
    return Array.isArray(data?.audits)
      ? data.audits
      : Array.isArray(data)
        ? data
        : [];
  }

  async listAuditsByStatus(status: string, userEmail?: string): Promise<any[]> {
    const params = new URLSearchParams();
    if (userEmail) params.set("user_email", userEmail);
    const url = params.toString()
      ? `${this.baseUrl}/api/v1/audits/status/${encodeURIComponent(status)}?${params}`
      : `${this.baseUrl}/api/v1/audits/status/${encodeURIComponent(status)}`;
    const res = await fetchWithBackendAuth(url);
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    const data = await res.json();
    return Array.isArray(data?.audits)
      ? data.audits
      : Array.isArray(data)
        ? data
        : [];
  }

  async getAudit(id: string): Promise<AuditSummary> {
    const res = await fetchWithBackendAuth(`${this.baseUrl}/api/v1/audits/${id}`);
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async deleteAudit(id: number): Promise<void> {
    const res = await fetchWithBackendAuth(`${this.baseUrl}/api/v1/audits/${id}`, {
      method: "DELETE",
    });
    if (!res.ok) throw new Error(`API error: ${res.status}`);
  }

  async getAuditStatus(id: string): Promise<AuditSummary> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/audits/${id}/status`,
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async getAuditPages(auditId: string): Promise<PageAudit[]> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/audits/${auditId}/pages`,
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async getPageDetails(auditId: string, pageId: string): Promise<PageAudit> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/audits/${auditId}/pages/${pageId}`,
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async getCompetitorData(auditId: string): Promise<CompetitorData[]> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/audits/${auditId}/competitors`,
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async getAuditReport(auditId: number): Promise<any> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/audits/${auditId}/report`,
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async getFixPlan(auditId: number): Promise<any> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/audits/${auditId}/fix_plan`,
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  // New Feature Methods

  async analyzeBacklinks(
    auditId: string,
    domain: string,
  ): Promise<import("./types").Backlink[]> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/backlinks/analyze/${auditId}?domain=${encodeURIComponent(domain)}`,
      { method: "POST" },
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async getBacklinks(auditId: string): Promise<import("./types").Backlink[]> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/backlinks/${auditId}`,
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async researchKeywords(
    auditId: string,
    domain: string,
    seedKeywords?: string[],
  ): Promise<import("./types").Keyword[]> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/keywords/research/${auditId}?domain=${encodeURIComponent(domain)}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(seedKeywords || []),
      },
    );
    if (!res.ok) throw await this.buildApiError(res);
    return res.json();
  }

  async getKeywords(auditId: string): Promise<import("./types").Keyword[]> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/keywords/${auditId}`,
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async trackRankings(
    auditId: string,
    domain: string,
    keywords: string[],
  ): Promise<import("./types").RankTracking[]> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/rank-tracking/track/${auditId}?domain=${encodeURIComponent(domain)}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(keywords),
      },
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async getRankings(
    auditId: string,
  ): Promise<import("./types").RankTracking[]> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/rank-tracking/${auditId}`,
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async checkLLMVisibility(
    auditId: string,
    brandName: string,
    queries: string[],
  ): Promise<import("./types").LLMVisibility[]> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/llm-visibility/check/${auditId}?brand_name=${encodeURIComponent(brandName)}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(queries),
      },
    );
    if (!res.ok) throw await this.buildApiError(res);
    return res.json();
  }

  async getLLMVisibility(
    auditId: string,
  ): Promise<import("./types").LLMVisibility[]> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/llm-visibility/${auditId}`,
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async generateAIContent(
    auditId: string,
    domain: string,
    topics: string[],
  ): Promise<import("./types").AIContentSuggestion[]> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/ai-content/generate/${auditId}?domain=${encodeURIComponent(domain)}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(topics),
      },
    );
    if (!res.ok) throw await this.buildApiError(res);
    return res.json();
  }

  async getAIContent(
    auditId: string,
  ): Promise<import("./types").AIContentSuggestion[]> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/ai-content/${auditId}`,
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  // ============= REPORTS =============

  async getAuditReports(auditId: number): Promise<any> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/reports/audit/${auditId}`,
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async generatePDF(auditId: number): Promise<any> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/audits/${auditId}/generate-pdf`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      },
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async downloadReport(reportId: number): Promise<Blob> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/reports/download/${reportId}`,
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.blob();
  }

  async getMarkdownReport(
    auditId: number,
  ): Promise<{ audit_id: number; markdown: string; created_at: string }> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/reports/markdown/${auditId}`,
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async getJSONReport(auditId: number): Promise<any> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/reports/json/${auditId}`,
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  // ============= ANALYTICS =============

  async getAuditAnalytics(auditId: number): Promise<any> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/analytics/audit/${auditId}`,
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async getCompetitorAnalysis(auditId: number): Promise<any> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/analytics/competitors/${auditId}`,
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async getDashboardData(): Promise<any> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/analytics/dashboard`,
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async getIssuesByPriority(auditId: number): Promise<any> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/analytics/issues/${auditId}`,
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  // ============= GEO FEATURES (COMPLETO) =============

  async startCitationTracking(
    auditId: number,
    industry = "general",
    keywords: string[] = [],
    llmName = "kimi",
  ): Promise<any> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/geo/citation-tracking/start`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          audit_id: auditId,
          industry,
          keywords,
          llm_name: llmName,
        }),
      },
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async getCitationHistory(auditId: number, days = 30): Promise<any> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/geo/citation-tracking/history/${auditId}?days=${encodeURIComponent(days.toString())}`,
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async getRecentCitations(auditId: number, limit = 10): Promise<any> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/geo/citation-tracking/recent/${auditId}?limit=${encodeURIComponent(limit.toString())}`,
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async discoverQueries(
    brandName: string,
    domain: string,
    industry: string,
    keywords: string[],
  ): Promise<any> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/geo/query-discovery/discover`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          brand_name: brandName,
          domain,
          industry,
          keywords,
        }),
      },
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async getQueryOpportunities(auditId: number, limit = 10): Promise<any> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/geo/query-discovery/opportunities/${auditId}?limit=${limit}`,
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async analyzeCompetitorCitations(
    auditId: number,
    competitorDomains: string[],
    queries: string[],
  ): Promise<any> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/geo/competitor-analysis/analyze`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          audit_id: auditId,
          competitor_domains: competitorDomains,
          queries,
        }),
      },
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async getCitationBenchmark(auditId: number): Promise<any> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/geo/competitor-analysis/benchmark/${auditId}`,
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async generateSchema(
    htmlContent: string,
    url: string,
    pageType?: string,
  ): Promise<any> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/geo/schema/generate`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          html_content: htmlContent,
          url,
          page_type: pageType,
        }),
      },
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async generateMultipleSchemas(
    htmlContent: string,
    url: string,
  ): Promise<any> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/geo/schema/multiple`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ html_content: htmlContent, url }),
      },
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async listContentTemplates(): Promise<any> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/geo/content-templates/list`,
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async generateContentTemplate(
    templateType: string,
    topic: string,
    keywords: string[],
  ): Promise<any> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/geo/content-templates/generate`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ template_type: templateType, topic, keywords }),
      },
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async analyzeContentForGEO(content: string): Promise<any> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/geo/content-templates/analyze`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(content),
      },
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async getGeoDashboard(auditId: number): Promise<any> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/geo/dashboard/${auditId}`,
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  // ============= CONTENT ANALYSIS (COMPLETO) =============

  async findDuplicates(pages: any[], threshold = 0.85): Promise<any> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/content/duplicates?threshold=${threshold}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(pages),
      },
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async extractKeywords(html: string, topN = 50): Promise<any> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/content/keywords/extract?top_n=${topN}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(html),
      },
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async analyzeKeywordGap(
    yourKeywords: any[],
    competitorKeywords: any[],
  ): Promise<any> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/content/keywords/gap`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          your_keywords: yourKeywords,
          competitor_keywords: competitorKeywords,
        }),
      },
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async compareKeywords(yourUrl: string, competitorUrl: string): Promise<any> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/content/keywords/compare?your_url=${encodeURIComponent(yourUrl)}&competitor_url=${encodeURIComponent(competitorUrl)}`,
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  // ============= CONTENT EDITOR =============

  async analyzeContent(text: string, keyword: string): Promise<any> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/tools/content-editor/analyze`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, keyword }),
      },
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  // ============= PAGESPEED =============

  async comparePageSpeed(url: string): Promise<any> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/pagespeed/compare?url=${encodeURIComponent(url)}`,
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async analyzePageSpeed(
    url: string,
    strategy: "mobile" | "desktop" = "mobile",
  ): Promise<any> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/pagespeed/analyze?url=${encodeURIComponent(url)}&strategy=${encodeURIComponent(strategy)}`,
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  // ============= HEALTH =============

  async getHealth(): Promise<any> {
    const res = await fetchWithBackendAuth(`${this.baseUrl}/health`);
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async getReadiness(): Promise<any> {
    const res = await fetchWithBackendAuth(`${this.baseUrl}/health/ready`);
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async getLiveness(): Promise<any> {
    const res = await fetchWithBackendAuth(`${this.baseUrl}/health/live`);
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async getStats(): Promise<any> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/audits/stats/summary`,
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  // ============= HUBSPOT =============

  async getHubSpotAuthUrl(): Promise<{ url: string; state: string }> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/hubspot/auth-url`,
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async hubSpotCallback(code: string, state: string): Promise<any> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/hubspot/callback`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code, state }),
      },
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async getHubSpotConnections(): Promise<any[]> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/hubspot/connections`,
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    const data = await res.json();
    return Array.isArray(data) ? data : [];
  }

  async syncHubSpot(connectionId: string): Promise<any> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/hubspot/sync/${encodeURIComponent(connectionId)}`,
      { method: "POST" },
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async getHubSpotPages(connectionId: string): Promise<any[]> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/hubspot/pages/${encodeURIComponent(connectionId)}`,
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    const data = await res.json();
    return Array.isArray(data) ? data : [];
  }

  async getHubSpotRecommendations(auditId: number): Promise<any> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/hubspot/recommendations/${auditId}`,
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async applyHubSpotRecommendations(
    auditId: number,
    recommendations: any[],
  ): Promise<any> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/hubspot/apply-recommendations`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ audit_id: auditId, recommendations }),
      },
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async rollbackHubSpotChange(changeId: string): Promise<any> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/hubspot/rollback/${encodeURIComponent(changeId)}`,
      { method: "POST" },
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  // ============= WEBHOOKS =============

  async listWebhookEvents(): Promise<any[]> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/webhooks/events`,
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    const data = await res.json();
    return Array.isArray(data) ? data : [];
  }

  async configureWebhook(config: {
    url: string;
    secret?: string | null;
    events: string[];
    active?: boolean;
    description?: string | null;
  }): Promise<any> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/webhooks/config`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url: config.url,
          secret: config.secret ?? null,
          events: config.events,
          active: config.active ?? true,
          description: config.description ?? null,
        }),
      },
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async testWebhook(request: {
    url: string;
    secret?: string | null;
    event_type?: string;
  }): Promise<any> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/webhooks/test`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url: request.url,
          secret: request.secret ?? null,
          event_type: request.event_type ?? "audit.completed",
        }),
      },
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async getWebhooksHealth(): Promise<any> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/webhooks/health`,
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  // ============= GITHUB =============

  async getGitHubAuthUrl(): Promise<{ url: string; state: string }> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/github/auth-url`,
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async githubCallback(code: string, state: string): Promise<any> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/github/callback`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code, state }),
      },
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async getGitHubConnections(): Promise<any[]> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/github/connections`,
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    const data = await res.json();
    return Array.isArray(data) ? data : [];
  }

  async syncGitHub(connectionId: string): Promise<any> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/github/sync/${encodeURIComponent(connectionId)}`,
      { method: "POST" },
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async getGitHubRepos(connectionId: string): Promise<any[]> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/github/repos/${encodeURIComponent(connectionId)}`,
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    const data = await res.json();
    return Array.isArray(data) ? data : [];
  }

  async analyzeGitHubRepo(connectionId: string, repoId: string): Promise<any> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/github/analyze/${encodeURIComponent(connectionId)}/${encodeURIComponent(repoId)}`,
      { method: "POST" },
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async createGitHubPR(request: {
    connection_id: string;
    repo_id: string;
    audit_id: number;
    fixes: any[];
  }): Promise<any> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/github/create-pr`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
      },
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async listGitHubPRs(repoId: string): Promise<any[]> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/github/prs/${encodeURIComponent(repoId)}`,
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    const data = await res.json();
    return Array.isArray(data) ? data : [];
  }

  async auditBlogs(connectionId: string, repoId: string): Promise<any> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/github/audit-blogs/${encodeURIComponent(connectionId)}/${encodeURIComponent(repoId)}`,
      { method: "POST" },
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async createBlogFixesPR(
    connectionId: string,
    repoId: string,
    blogPaths: string[],
  ): Promise<any> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/github/create-blog-fixes-pr/${encodeURIComponent(connectionId)}/${encodeURIComponent(repoId)}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(blogPaths),
      },
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async auditToFixes(auditId: number): Promise<any> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/github/audit-to-fixes/${auditId}`,
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async getGitHubGeoScore(auditId: number): Promise<any> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/github/geo-score/${auditId}`,
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async auditBlogsGeo(connectionId: string, repoId: string): Promise<any> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/github/audit-blogs-geo/${encodeURIComponent(connectionId)}/${encodeURIComponent(repoId)}`,
      { method: "POST" },
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async createGeoFixesPR(
    connectionId: string,
    repoId: string,
    blogPaths: string[],
    includeGeo = true,
  ): Promise<any> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/github/create-geo-fixes-pr/${encodeURIComponent(connectionId)}/${encodeURIComponent(repoId)}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          blog_paths: blogPaths,
          include_geo: includeGeo,
        }),
      },
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async geoCompare(auditId: number, competitorUrls?: string[]): Promise<any> {
    const qs = competitorUrls?.length
      ? `?${competitorUrls.map((u) => `competitor_urls=${encodeURIComponent(u)}`).join("&")}`
      : "";
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/github/geo-compare/${auditId}${qs}`,
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async createAutoFixPR(
    connectionId: string,
    repoId: string,
    auditId: number,
  ): Promise<any> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/github/create-auto-fix-pr/${encodeURIComponent(connectionId)}/${encodeURIComponent(repoId)}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ audit_id: auditId }),
      },
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  // ============= SCORE HISTORY =============

  async getScoreHistory(domain: string, days = 90): Promise<any> {
    const params = new URLSearchParams({ days: days.toString() });
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/score-history/domain/${encodeURIComponent(domain)}?${params}`,
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async getMonthlyComparison(domain: string): Promise<any> {
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/score-history/domain/${encodeURIComponent(domain)}/comparison`,
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async getDomainsSummary(days = 30): Promise<any> {
    const params = new URLSearchParams({ days: days.toString() });
    const res = await fetchWithBackendAuth(
      `${this.baseUrl}/api/v1/score-history/summary?${params}`,
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }
}

export const api = new APIService();

