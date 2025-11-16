import type { AuditSummary, PageAudit, CompetitorData } from './types'

// En el navegador usa localhost, en el servidor usa el nombre del servicio Docker
const API_URL = typeof window !== 'undefined' 
  ? (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000')
  : (process.env.API_URL || 'http://backend:8000');

class APIService {
  private baseUrl = API_URL;

  async searchAI(query: string): Promise<{ response: string; suggestions: string[] }> {
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
}

export const api = new APIService()
