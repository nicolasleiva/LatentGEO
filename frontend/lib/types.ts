// Type definitions for AI Audit Studio

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
