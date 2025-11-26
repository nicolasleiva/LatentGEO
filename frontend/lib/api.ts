import type { AuditSummary, PageAudit, CompetitorData } from './types'

// En el navegador usa localhost, en el servidor usa el nombre del servicio Docker
const API_URL = typeof window !== 'undefined'
  ? (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000')
  : (process.env.API_URL || 'http://backend:8000');

class APIService {
  private baseUrl = API_URL;

  async searchAI(query: string): Promise<{ response: string; suggestions: string[]; audit_started?: boolean; audit_id?: number }> {
    const res = await fetch(`${this.baseUrl}/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query })
    })
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json()
  }

  async createAudit(config: {
    url: string
    maxPages?: number
    competitors?: string[]
  }): Promise<AuditSummary> {
    const res = await fetch(`${this.baseUrl}/api/audits`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config)
    })
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json()
  }

  async getAudit(id: string): Promise<AuditSummary> {
    const res = await fetch(`${this.baseUrl}/api/audits/${id}`)
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json()
  }

  async getAuditPages(auditId: string): Promise<PageAudit[]> {
    const res = await fetch(`${this.baseUrl}/api/audits/${auditId}/pages`)
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json()
  }

  async getPageDetails(auditId: string, pageId: string): Promise<PageAudit> {
    const res = await fetch(`${this.baseUrl}/api/audits/${auditId}/pages/${pageId}`)
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json()
  }

  async getCompetitorData(auditId: string): Promise<CompetitorData[]> {
    const res = await fetch(`${this.baseUrl}/api/audits/${auditId}/competitors`)
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json()
  }

  // New Feature Methods

  async analyzeBacklinks(auditId: string, domain: string): Promise<import('./types').Backlink[]> {
    const res = await fetch(`${this.baseUrl}/api/backlinks/analyze/${auditId}?domain=${domain}`, { method: 'POST' })
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json()
  }

  async getBacklinks(auditId: string): Promise<import('./types').Backlink[]> {
    const res = await fetch(`${this.baseUrl}/api/backlinks/${auditId}`)
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json()
  }

  async researchKeywords(auditId: string, domain: string, seedKeywords?: string[]): Promise<import('./types').Keyword[]> {
    const res = await fetch(`${this.baseUrl}/api/keywords/research/${auditId}?domain=${domain}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(seedKeywords || [])
    })
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json()
  }

  async getKeywords(auditId: string): Promise<import('./types').Keyword[]> {
    const res = await fetch(`${this.baseUrl}/api/keywords/${auditId}`)
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json()
  }

  async trackRankings(auditId: string, domain: string, keywords: string[]): Promise<import('./types').RankTracking[]> {
    const res = await fetch(`${this.baseUrl}/api/rank-tracking/track/${auditId}?domain=${domain}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(keywords)
    })
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json()
  }

  async getRankings(auditId: string): Promise<import('./types').RankTracking[]> {
    const res = await fetch(`${this.baseUrl}/api/rank-tracking/${auditId}`)
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json()
  }

  async checkLLMVisibility(auditId: string, brandName: string, queries: string[]): Promise<import('./types').LLMVisibility[]> {
    const res = await fetch(`${this.baseUrl}/api/llm-visibility/check/${auditId}?brand_name=${brandName}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(queries)
    })
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json()
  }

  async getLLMVisibility(auditId: string): Promise<import('./types').LLMVisibility[]> {
    const res = await fetch(`${this.baseUrl}/api/llm-visibility/${auditId}`)
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json()
  }

  async generateAIContent(auditId: string, domain: string, topics: string[]): Promise<import('./types').AIContentSuggestion[]> {
    const res = await fetch(`${this.baseUrl}/api/ai-content/generate/${auditId}?domain=${domain}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(topics)
    })
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json()
  }

  async getAIContent(auditId: string): Promise<import('./types').AIContentSuggestion[]> {
    const res = await fetch(`${this.baseUrl}/api/ai-content/${auditId}`)
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json()
  }

  // ============= REPORTS =============

  async getAuditReports(auditId: number): Promise<any> {
    const res = await fetch(`${this.baseUrl}/reports/audit/${auditId}`)
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json()
  }

  async generatePDF(auditId: number, includeCompetitorAnalysis = false, includeRawData = false): Promise<{ task_id: string; audit_id: number; status: string }> {
    const res = await fetch(`${this.baseUrl}/reports/generate-pdf`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ audit_id: auditId, include_competitor_analysis: includeCompetitorAnalysis, include_raw_data: includeRawData })
    })
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json()
  }

  async downloadReport(reportId: number): Promise<Blob> {
    const res = await fetch(`${this.baseUrl}/reports/download/${reportId}`)
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.blob()
  }

  async getMarkdownReport(auditId: number): Promise<{ audit_id: number; markdown: string; created_at: string }> {
    const res = await fetch(`${this.baseUrl}/reports/markdown/${auditId}`)
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json()
  }

  async getJSONReport(auditId: number): Promise<any> {
    const res = await fetch(`${this.baseUrl}/reports/json/${auditId}`)
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json()
  }

  // ============= ANALYTICS =============

  async getAuditAnalytics(auditId: number): Promise<any> {
    const res = await fetch(`${this.baseUrl}/analytics/audit/${auditId}`)
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json()
  }

  async getCompetitorAnalysis(auditId: number): Promise<any> {
    const res = await fetch(`${this.baseUrl}/analytics/competitors/${auditId}`)
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json()
  }

  async getDashboardData(): Promise<any> {
    const res = await fetch(`${this.baseUrl}/analytics/dashboard`)
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json()
  }

  async getIssuesByPriority(auditId: number): Promise<any> {
    const res = await fetch(`${this.baseUrl}/analytics/issues/${auditId}`)
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json()
  }

  // ============= GEO FEATURES (COMPLETO) =============

  async startCitationTracking(auditId: number, industry = 'general', keywords: string[] = [], llmName = 'kimi'): Promise<any> {
    const res = await fetch(`${this.baseUrl}/api/geo/citation-tracking/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ audit_id: auditId, industry, keywords, llm_name: llmName })
    })
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json()
  }

  async getCitationHistory(auditId: number, days = 30): Promise<any> {
    const res = await fetch(`${this.baseUrl}/api/geo/citation-tracking/history/${auditId}?days=${days}`)
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json()
  }

  async getRecentCitations(auditId: number, limit = 10): Promise<any> {
    const res = await fetch(`${this.baseUrl}/api/geo/citation-tracking/recent/${auditId}?limit=${limit}`)
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json()
  }

  async discoverQueries(brandName: string, domain: string, industry: string, keywords: string[]): Promise<any> {
    const res = await fetch(`${this.baseUrl}/api/geo/query-discovery/discover`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ brand_name: brandName, domain, industry, keywords })
    })
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json()
  }

  async getQueryOpportunities(auditId: number, limit = 10): Promise<any> {
    const res = await fetch(`${this.baseUrl}/api/geo/query-discovery/opportunities/${auditId}?limit=${limit}`)
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json()
  }

  async analyzeCompetitorCitations(auditId: number, competitorDomains: string[], queries: string[]): Promise<any> {
    const res = await fetch(`${this.baseUrl}/api/geo/competitor-analysis/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ audit_id: auditId, competitor_domains: competitorDomains, queries })
    })
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json()
  }

  async getCitationBenchmark(auditId: number): Promise<any> {
    const res = await fetch(`${this.baseUrl}/api/geo/competitor-analysis/benchmark/${auditId}`)
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json()
  }

  async generateSchema(htmlContent: string, url: string, pageType?: string): Promise<any> {
    const res = await fetch(`${this.baseUrl}/api/geo/schema/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ html_content: htmlContent, url, page_type: pageType })
    })
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json()
  }

  async generateMultipleSchemas(htmlContent: string, url: string): Promise<any> {
    const res = await fetch(`${this.baseUrl}/api/geo/schema/multiple`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ html_content: htmlContent, url })
    })
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json()
  }

  async listContentTemplates(): Promise<any> {
    const res = await fetch(`${this.baseUrl}/api/geo/content-templates/list`)
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json()
  }

  async generateContentTemplate(templateType: string, topic: string, keywords: string[]): Promise<any> {
    const res = await fetch(`${this.baseUrl}/api/geo/content-templates/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ template_type: templateType, topic, keywords })
    })
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json()
  }

  async analyzeContentForGEO(content: string): Promise<any> {
    const res = await fetch(`${this.baseUrl}/api/geo/content-templates/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(content)
    })
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json()
  }

  async getGeoDashboard(auditId: number): Promise<any> {
    const res = await fetch(`${this.baseUrl}/api/geo/dashboard/${auditId}`)
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json()
  }

  // ============= CONTENT ANALYSIS (COMPLETO) =============

  async findDuplicates(pages: any[], threshold = 0.85): Promise<any> {
    const res = await fetch(`${this.baseUrl}/api/content/duplicates?threshold=${threshold}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(pages)
    })
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json()
  }

  async extractKeywords(html: string, topN = 50): Promise<any> {
    const res = await fetch(`${this.baseUrl}/api/content/keywords/extract?top_n=${topN}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(html)
    })
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json()
  }

  async analyzeKeywordGap(yourKeywords: any[], competitorKeywords: any[]): Promise<any> {
    const res = await fetch(`${this.baseUrl}/api/content/keywords/gap`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ your_keywords: yourKeywords, competitor_keywords: competitorKeywords })
    })
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json()
  }

  async compareKeywords(yourUrl: string, competitorUrl: string): Promise<any> {
    const res = await fetch(`${this.baseUrl}/api/content/keywords/compare?your_url=${encodeURIComponent(yourUrl)}&competitor_url=${encodeURIComponent(competitorUrl)}`)
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json()
  }

  // ============= CONTENT EDITOR =============

  async analyzeContent(text: string, keyword: string): Promise<any> {
    const res = await fetch(`${this.baseUrl}/api/tools/content-editor/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, keyword })
    })
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json()
  }

  // ============= PAGESPEED =============

  async comparePageSpeed(url: string): Promise<any> {
    const res = await fetch(`${this.baseUrl}/api/pagespeed/compare?url=${encodeURIComponent(url)}`)
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json()
  }

  // ============= HEALTH =============

  async getHealth(): Promise<any> {
    const res = await fetch(`${this.baseUrl}/health`)
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json()
  }

  async getDbHealth(): Promise<any> {
    const res = await fetch(`${this.baseUrl}/db-health`)
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json()
  }

  async getStats(): Promise<any> {
    const res = await fetch(`${this.baseUrl}/stats`)
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json()
  }
}

export const api = new APIService()
