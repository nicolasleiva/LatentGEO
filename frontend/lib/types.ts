// Type definitions for LatentGEO.ai

export interface AuditSummary {
  id: string
  url: string
  status: 'pending' | 'crawling' | 'analyzing' | 'completed' | 'failed'
  createdAt: string
  completedAt?: string
  progress: {
    percentage: number
    currentStage: string
    stagesCompleted: string[]
  }
  scores: {
    overall: number
    structure: number
    content: number
    eeat: number
    schema: number
  }
  stats: {
    totalPages: number
    issuesFound: number
    criticalIssues: number
    warningIssues: number
    recommendations: number
  }
  subdomains?: string[]
  competitors?: string[]
}

export interface PageAudit {
  id: string
  auditId: string
  url: string
  path: string
  title: string
  scores: {
    overall: number
    structure: number
    content: number
    eeat: number
    schema: number
  }
  issues: Issue[]
  lastCrawled: string
  status: 'pass' | 'warning' | 'fail'
}

export interface Issue {
  id: string
  severity: 'critical' | 'warning' | 'info'
  category: 'structure' | 'content' | 'eeat' | 'schema' | 'performance'
  title: string
  description: string
  affectedElements?: string[]
  recommendation: string
  aiSuggestion?: string
  fixPlan?: FixStep[]
}

export interface FixStep {
  step: number
  action: string
  code?: string
  explanation: string
}

export interface CompetitorData {
  url: string
  scores: {
    overall: number
    structure: number
    content: number
    eeat: number
    schema: number
  }
}

export interface ConversationMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: string
  suggestions?: string[]
  audit_id?: number
  audit_started?: boolean
}

// New Feature Types

export interface Backlink {
  id: number
  source_url: string
  target_url: string
  anchor_text: string
  is_dofollow: boolean
  domain_authority?: number
}

export interface Keyword {
  id: number
  term: string
  volume: number
  difficulty: number
  cpc: number
  intent: string
}

export interface RankTracking {
  id: number
  keyword: string
  position: number
  url: string
  device: string
  location: string
  tracked_at: string
}

export interface LLMVisibility {
  id: number
  llm_name: string
  query: string
  is_visible: boolean
  rank?: number
  citation_text?: string
  checked_at: string
}

export interface AIContentSuggestion {
  id: number
  page_url?: string
  topic: string
  suggestion_type: string
  content_outline?: any
  priority: string
  created_at: string
}

export interface ReportItem {
  id: number
  audit_id: number
  report_type?: string
  file_path?: string
  created_at?: string
}

export interface WebhookEventDescriptor {
  event: string
  description: string
}

export interface WebhookTestResponse {
  success: boolean
  status_code?: number
  response_time_ms?: number
  error?: string
}

export interface GitHubConnection {
  id: string
  provider?: string
  account_login?: string
  created_at?: string
  is_active?: boolean
}

export interface GitHubRepository {
  id: string
  connection_id: string
  name?: string
  full_name?: string
  html_url?: string
  default_branch?: string
  is_active?: boolean
}

export interface GitHubPullRequest {
  id?: string
  pr_number: number
  title?: string
  status?: string
  html_url?: string
  created_at?: string
}

export interface FixInputField {
  key: string
  label: string
  value?: string
  placeholder?: string
  required?: boolean
  input_type?: 'text' | 'textarea'
}

export interface FixInputGroup {
  id: string
  issue_code: string
  page_path: string
  required?: boolean
  prompt?: string
  fields: FixInputField[]
}

export interface FixInputsResponse {
  audit_id: number
  missing_inputs: FixInputGroup[]
  missing_required: number
}

export interface FixInputsSubmit {
  inputs: Array<{
    id: string
    issue_code: string
    page_path: string
    values: Record<string, any>
  }>
}

export interface FixInputChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface FixInputChatRequest {
  issue_code: string
  field_key: string
  field_label?: string
  placeholder?: string
  current_values?: Record<string, any>
  language?: string
  history?: FixInputChatMessage[]
}

export interface FixInputChatResponse {
  assistant_message: string
  suggested_value: string
  confidence: 'evidence' | 'unknown'
}
