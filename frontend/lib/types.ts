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
