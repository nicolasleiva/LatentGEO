import type { AuditSummary, PageAudit, CompetitorData } from '@/lib/types'

export const demoAudit: AuditSummary = {
  id: 'demo_audit_001',
  url: 'https://example.com',
  status: 'completed',
  createdAt: '2025-01-14T10:00:00Z',
  completedAt: '2025-01-14T10:15:00Z',
  progress: {
    percentage: 100,
    currentStage: 'Complete',
    stagesCompleted: ['Crawling', 'Analysis', 'Scoring', 'Recommendations']
  },
  scores: {
    overall: 78,
    structure: 85,
    content: 72,
    eeat: 68,
    schema: 82
  },
  stats: {
    totalPages: 247,
    issuesFound: 156,
    criticalIssues: 12,
    warningIssues: 89,
    recommendations: 45
  },
  subdomains: ['www', 'blog', 'shop', 'docs'],
  competitors: ['competitor1.com', 'competitor2.com']
}

export const demoPages: PageAudit[] = [
  {
    id: 'page_001',
    auditId: 'demo_audit_001',
    url: 'https://example.com/',
    path: '/',
    title: 'Home - Example Site',
    scores: {
      overall: 85,
      structure: 90,
      content: 82,
      eeat: 75,
      schema: 88
    },
    issues: [
      {
        id: 'issue_001',
        severity: 'warning',
        category: 'content',
        title: 'Meta description could be more compelling',
        description: 'The meta description is present but could be optimized for better CTR.',
        recommendation: 'Rewrite to include primary keywords and a clear value proposition.',
        aiSuggestion: 'Try: "Discover premium solutions for [your niche]. Trusted by 10,000+ customers worldwide. Get started free today."'
      }
    ],
    lastCrawled: '2025-01-14T10:15:00Z',
    status: 'pass'
  },
  {
    id: 'page_002',
    auditId: 'demo_audit_001',
    url: 'https://example.com/products',
    path: '/products',
    title: 'Our Products',
    scores: {
      overall: 72,
      structure: 78,
      content: 68,
      eeat: 65,
      schema: 75
    },
    issues: [
      {
        id: 'issue_002',
        severity: 'critical',
        category: 'structure',
        title: 'Missing H1 heading',
        description: 'Page does not have an H1 heading, which is critical for SEO.',
        affectedElements: ['body > main'],
        recommendation: 'Add a descriptive H1 heading at the top of the page content.',
        aiSuggestion: 'Add <h1>Explore Our Product Range</h1> as the main heading.',
        fixPlan: [
          {
            step: 1,
            action: 'Locate the main content container',
            code: '<main>\n  <!-- Add H1 here -->\n  <h1>Explore Our Product Range</h1>',
            explanation: 'Insert H1 as the first element in your main content area'
          }
        ]
      },
      {
        id: 'issue_003',
        severity: 'warning',
        category: 'schema',
        title: 'Product schema missing',
        description: 'Products lack structured data markup for better search visibility.',
        recommendation: 'Implement Product schema markup for all product listings.',
        aiSuggestion: 'Add JSON-LD schema with name, price, availability, and reviews.'
      }
    ],
    lastCrawled: '2025-01-14T10:15:00Z',
    status: 'warning'
  },
  {
    id: 'page_003',
    auditId: 'demo_audit_001',
    url: 'https://example.com/about',
    path: '/about',
    title: 'About Us - Example Site',
    scores: {
      overall: 65,
      structure: 70,
      content: 60,
      eeat: 58,
      schema: 72
    },
    issues: [
      {
        id: 'issue_004',
        severity: 'critical',
        category: 'eeat',
        title: 'No author information or credentials',
        description: 'The about page lacks clear author information and credentials, weakening E-E-A-T signals.',
        recommendation: 'Add author bios, credentials, and social proof elements.',
        aiSuggestion: 'Include team member profiles with names, titles, LinkedIn profiles, and relevant certifications.'
      }
    ],
    lastCrawled: '2025-01-14T10:15:00Z',
    status: 'fail'
  }
]

export const demoCompetitors: CompetitorData[] = [
  {
    url: 'example.com',
    scores: {
      overall: 78,
      structure: 85,
      content: 72,
      eeat: 68,
      schema: 82
    }
  },
  {
    url: 'competitor1.com',
    scores: {
      overall: 85,
      structure: 88,
      content: 82,
      eeat: 80,
      schema: 90
    }
  },
  {
    url: 'competitor2.com',
    scores: {
      overall: 72,
      structure: 75,
      content: 70,
      eeat: 65,
      schema: 78
    }
  }
]
