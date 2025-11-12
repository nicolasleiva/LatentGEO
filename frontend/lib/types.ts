export type AuditStatus = "PENDING" | "RUNNING" | "COMPLETED" | "FAILED"

export interface Audit {
  id: number
  url: string
  domain: string
  status: AuditStatus
  progress: number
  created_at: string
  started_at?: string
  completed_at?: string
  is_ymyl?: boolean
  category?: string
  total_pages?: number
  critical_issues: number
  high_issues: number
  medium_issues: number
  low_issues: number
  error_message?: string
  report_pdf_path?: string
}

export interface CreateAuditRequest {
  url: string
  max_crawl?: number
  max_audit?: number
}
