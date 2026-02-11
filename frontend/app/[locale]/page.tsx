'use client'

import { useState, useEffect, useMemo, useCallback } from 'react'
import { usePathname, useRouter } from 'next/navigation'
import { useUser } from '@auth0/nextjs-auth0/client'
import { API_URL } from '@/lib/api'
import { fetchWithBackendAuth } from '@/lib/backend-auth'
import {
  Search,
  ArrowRight,
  Activity,
  Globe,
  Clock,
  Sparkles,
  Shield,
  Zap,
  BarChart3,
  Target,
  Link as LinkIcon,
  Gauge,
  Bot,
  Rocket,
  GitPullRequest,
  ScrollText,
  FileText,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Header } from '@/components/header'
import { cn } from '@/lib/utils'

interface Audit {
  id: number
  url: string
  domain: string
  status: string
  created_at: string
  geo_score?: number
}

const featureCards = [
  {
    title: 'Keyword Discovery',
    description: 'Map high-intent keyword clusters and topic gaps before your competitors.',
    icon: Search,
    tag: 'Keywords',
  },
  {
    title: 'AI Ranking Visibility',
    description: 'Track how your brand appears in AI answers and monitor ranking drift.',
    icon: BarChart3,
    tag: 'AI Ranking',
  },
  {
    title: 'GEO Priority Score',
    description: 'Prioritize fixes by impact with a single GEO score tied to real outcomes.',
    icon: Target,
    tag: 'GEO',
  },
  {
    title: 'Competitor Radar',
    description: 'Benchmark competitor coverage, citations, and strategy in one workspace.',
    icon: Globe,
    tag: 'Competitive',
  },
  {
    title: 'Backlink Intelligence',
    description: 'Find backlink opportunities and authority gaps worth immediate action.',
    icon: LinkIcon,
    tag: 'Backlinks',
  },
  {
    title: 'PageSpeed Diagnostics',
    description: 'Surface technical bottlenecks with lab + field data and guided remediation.',
    icon: Gauge,
    tag: 'Performance',
  },
  {
    title: 'AI Content Blueprint',
    description: 'Generate outlines, FAQs, and structure templates aligned with search intent.',
    icon: ScrollText,
    tag: 'Content',
  },
  {
    title: 'GitHub Auto-Fix',
    description: 'Turn findings into pull requests with proposed fixes, tests, and guardrails.',
    icon: GitPullRequest,
    tag: 'Dev Workflow',
  },
  {
    title: 'Live Agent Chat',
    description: 'Drive each audit through a guided AI flow tailored to your market goals.',
    icon: Bot,
    tag: 'Assistant',
  },
  {
    title: 'PDF & Exports',
    description: 'Share executive-ready reports and raw exports for faster execution.',
    icon: FileText,
    tag: 'Reporting',
  },
]

export default function HomePage() {
  const router = useRouter()
  const pathname = usePathname()
  const { user, isLoading: authLoading } = useUser()
  const [url, setUrl] = useState('')
  const [audits, setAudits] = useState<Audit[]>([])
  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [visibleFeatures, setVisibleFeatures] = useState(0)

  const backendUrl = API_URL

  const localePrefix = useMemo(() => {
    const segment = pathname?.split('/').filter(Boolean)[0]
    return segment === 'es' || segment === 'en' ? `/${segment}` : '/en'
  }, [pathname])

  const localePath = useCallback((path: string) => {
    const normalized = path.startsWith('/') ? path : `/${path}`
    if (normalized === '/') return localePrefix
    if (normalized.startsWith('/en/') || normalized.startsWith('/es/')) return normalized
    return `${localePrefix}${normalized}`
  }, [localePrefix])

  useEffect(() => {
    const timer = window.setInterval(() => {
      setVisibleFeatures(prev => (prev >= featureCards.length ? featureCards.length : prev + 1))
    }, 100)
    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    if (user && !authLoading) {
      setLoading(true)
      fetchWithBackendAuth(`${backendUrl}/api/audits`)
        .then(res => res.json())
        .then(data => {
          const sorted = Array.isArray(data)
            ? data
              .sort((a: Audit, b: Audit) =>
                new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
              )
              .slice(0, 6)
            : []
          setAudits(sorted)
          setLoading(false)
        })
        .catch(err => {
          console.error('Error fetching audits:', err)
          setLoading(false)
        })
    }
  }, [user, authLoading, backendUrl])

  const handleAudit = async (e: React.FormEvent) => {
    e.preventDefault()
    e.stopPropagation()

    setError(null)

    if (!url || !url.trim()) {
      setError('Please enter a valid URL')
      return
    }

    try {
      new URL(url)
    } catch {
      setError('Please enter a valid URL (e.g., https://example.com)')
      return
    }

    if (!user) {
      sessionStorage.setItem('pendingAuditUrl', url)
      window.location.href = '/auth/login'
      return
    }

    setSubmitting(true)
    try {
      const endpoint = `${backendUrl}/api/audits/`.replace(/\/+$/, '/')
      const requestBody = {
        url: url.trim(),
      }

      const res = await fetchWithBackendAuth(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify(requestBody),
        credentials: 'include'
      })

      if (res.status === 307 || res.status === 308) {
        const location = res.headers.get('Location')
        if (location) {
          const redirectUrl = location.startsWith('http') ? location : `${backendUrl}${location}`
          const redirectRes = await fetchWithBackendAuth(redirectUrl, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Accept': 'application/json'
            },
            body: JSON.stringify(requestBody),
            credentials: 'include'
          })

          if (redirectRes.ok || redirectRes.status === 202) {
            const newAudit = await redirectRes.json()
            router.push(localePath(`/audits/${newAudit.id}`))
            return
          } else {
            throw new Error(`Error after redirect: ${redirectRes.status}`)
          }
        }
      }

      if (res.ok || res.status === 202) {
        const newAudit = await res.json()
        router.push(localePath(`/audits/${newAudit.id}`))
      } else {
        let errorText = 'Unknown error'
        try {
          const errorData = await res.text()
          errorText = errorData || `Error ${res.status}: ${res.statusText}`
        } catch {
          errorText = `Error ${res.status}: ${res.statusText}`
        }
        setError(`Failed to create audit (${res.status}): ${errorText}`)
        setSubmitting(false)
      }
    } catch (error: any) {
      console.error('Error creating audit:', error)
      const errorMessage = error.message || 'Please verify the server is running.'
      setError(`Connection error: ${errorMessage}`)
      setSubmitting(false)
    }
  }

  useEffect(() => {
    if (user && !authLoading) {
      const pendingUrl = sessionStorage.getItem('pendingAuditUrl')
      if (pendingUrl) {
        sessionStorage.removeItem('pendingAuditUrl')
        setUrl(pendingUrl)
      }
    }
  }, [user, authLoading])

  return (
    <div className="min-h-screen text-foreground">
      <Header />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-10 sm:py-14">
        <section className="relative overflow-hidden rounded-[2rem] border border-border/70 bg-card/80 p-6 sm:p-10 lg:p-14">
          <div className="absolute -top-20 -left-16 h-64 w-64 rounded-full bg-brand/10 blur-3xl" />
          <div className="absolute -bottom-20 -right-16 h-72 w-72 rounded-full bg-foreground/10 blur-3xl" />

          <div className="relative z-10 grid gap-12 lg:grid-cols-[1.08fr_0.92fr] items-start">
            <div className="space-y-8">
              <div className="inline-flex items-center gap-2 px-4 py-2 bg-foreground/5 border border-foreground/10 rounded-full text-foreground/80 text-sm">
                <Sparkles className="w-4 h-4 text-brand" />
                Production-ready GEO operating system
              </div>

              <h1 className="text-4xl md:text-6xl lg:text-7xl font-semibold tracking-tight leading-[0.95]">
                Minimal design.
                <br />
                Maximum growth signal.
              </h1>

              <p className="text-lg text-muted-foreground max-w-2xl leading-relaxed">
                LatentGEO.ai unifies keyword intelligence, AI ranking visibility, technical SEO diagnostics,
                and automated execution so teams can ship measurable outcomes faster.
              </p>

              <form onSubmit={handleAudit} className="max-w-2xl relative" id="start-audit">
                <div className="relative flex flex-col gap-2">
                  <div className="relative flex items-center glass-panel border border-border rounded-2xl p-2 shadow-2xl">
                    <Search className="w-5 h-5 text-muted-foreground ml-4" />
                    <input
                      type="url"
                      placeholder="Paste your website URL (e.g., https://example.com)"
                      className="flex-1 bg-transparent border-none text-foreground placeholder:text-muted-foreground focus:ring-0 px-4 py-4 outline-none text-base"
                      value={url}
                      onChange={(e) => {
                        setUrl(e.target.value)
                        setError(null)
                      }}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && !submitting) {
                          e.preventDefault()
                          handleAudit(e as any)
                        }
                      }}
                      required
                      disabled={submitting}
                    />
                    <button
                      type="submit"
                      disabled={submitting || !url.trim()}
                      className="glass-button-primary px-6 py-3 rounded-xl flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                      onClick={(e) => {
                        e.preventDefault()
                        handleAudit(e as any)
                      }}
                    >
                      {submitting ? (
                        <>
                          <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                          Running audit
                        </>
                      ) : (
                        <>
                          Start audit <ArrowRight className="w-5 h-5" />
                        </>
                      )}
                    </button>
                  </div>
                  {error && (
                    <div className="text-red-600 text-sm px-4 py-2 bg-red-500/10 border border-red-500/20 rounded-lg">
                      {error}
                    </div>
                  )}
                </div>
              </form>

              {!authLoading && !user && (
                <p className="text-muted-foreground text-sm">
                  <a href="/auth/login" className="text-brand hover:underline">Sign in</a>
                  {' '}to save your audits and track progress.
                </p>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="rounded-xl border border-border/70 bg-background/70 px-4 py-3">
                  <p className="text-xs uppercase tracking-wider text-muted-foreground">Coverage</p>
                  <p className="text-sm font-semibold mt-1">Keywords + AI + GEO</p>
                </div>
                <div className="rounded-xl border border-border/70 bg-background/70 px-4 py-3">
                  <p className="text-xs uppercase tracking-wider text-muted-foreground">Execution</p>
                  <p className="text-sm font-semibold mt-1">Auto PRs & Fix Plans</p>
                </div>
                <div className="rounded-xl border border-border/70 bg-background/70 px-4 py-3">
                  <p className="text-xs uppercase tracking-wider text-muted-foreground">Signal</p>
                  <p className="text-sm font-semibold mt-1">Live audit telemetry</p>
                </div>
              </div>
            </div>

            <div className="space-y-5">
              <div className="glass-card p-6 sm:p-7 relative overflow-hidden">
                <div className="absolute -top-16 -right-14 h-40 w-40 rounded-full bg-brand/20 blur-2xl" />
                <div className="relative z-10">
                  <p className="text-sm uppercase tracking-widest text-muted-foreground">Autonomous pipeline</p>
                  <h3 className="text-2xl font-semibold mt-2">Insights that execute themselves</h3>
                  <p className="text-sm text-muted-foreground mt-3">
                    Move from diagnosis to shipped improvements with a single workflow.
                  </p>
                </div>

                <div className="mt-5 space-y-3">
                  {[
                    'Keyword + intent clustering',
                    'AI ranking and citation visibility',
                    'Code-level remediation via GitHub PRs',
                  ].map((item) => (
                    <div key={item} className="flex items-center gap-3 text-sm text-foreground/85">
                      <div className="h-2 w-2 rounded-full bg-brand" />
                      {item}
                    </div>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="rounded-2xl border border-border/70 bg-background/75 p-5">
                  <div className="flex items-center justify-between">
                    <p className="text-xs uppercase tracking-wider text-muted-foreground">Live status</p>
                    <Activity className="h-4 w-4 text-brand" />
                  </div>
                  <p className="mt-3 text-2xl font-semibold">Realtime</p>
                  <p className="text-sm text-muted-foreground mt-1">SSE updates across the audit lifecycle.</p>
                </div>
                <div className="rounded-2xl border border-border/70 bg-background/75 p-5">
                  <div className="flex items-center justify-between">
                    <p className="text-xs uppercase tracking-wider text-muted-foreground">Secure workflow</p>
                    <Shield className="h-4 w-4 text-brand" />
                  </div>
                  <p className="mt-3 text-2xl font-semibold">Governed</p>
                  <p className="text-sm text-muted-foreground mt-1">Controlled rollout with approval points.</p>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="mt-16 sm:mt-20">
          <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4">
            <div>
              <p className="text-sm uppercase tracking-widest text-muted-foreground">Feature stack</p>
              <h2 className="text-3xl md:text-4xl font-semibold tracking-tight mt-2">
                From keywords to AI ranking control.
              </h2>
            </div>
            <p className="text-muted-foreground max-w-xl">
              Cards load progressively to highlight each capability: research, diagnostics, automation, and reporting.
            </p>
          </div>

          <div className="mt-8 grid sm:grid-cols-2 xl:grid-cols-5 gap-4">
            {featureCards.map((feature, index) => {
              const Icon = feature.icon
              const isVisible = index < visibleFeatures
              return (
                <article
                  key={feature.title}
                  className={cn(
                    'rounded-2xl border border-border/70 bg-card/75 p-5 transition-all duration-500 ease-out',
                    isVisible ? 'translate-y-0 opacity-100' : 'translate-y-4 opacity-0'
                  )}
                  style={{ transitionDelay: `${index * 45}ms` }}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="h-10 w-10 rounded-xl bg-brand/10 text-brand flex items-center justify-center">
                      <Icon className="h-5 w-5" />
                    </div>
                    <span className="text-[11px] uppercase tracking-widest text-muted-foreground">
                      {feature.tag}
                    </span>
                  </div>
                  <h3 className="text-base font-semibold mt-4">{feature.title}</h3>
                  <p className="text-sm text-muted-foreground mt-2 leading-relaxed">{feature.description}</p>
                </article>
              )
            })}
          </div>
        </section>

        {!authLoading && !user && (
          <section className="mt-14 sm:mt-16 grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-6 glass-card border-border/70">
              <div className="w-12 h-12 bg-brand/10 rounded-xl flex items-center justify-center mb-4 text-brand">
                <Globe className="w-6 h-6" />
              </div>
              <h3 className="text-lg font-semibold mb-2">Generative search coverage</h3>
              <p className="text-muted-foreground text-sm">
                Understand how your brand appears in AI answers and conversational search.
              </p>
            </div>
            <div className="p-6 glass-card border-border/70">
              <div className="w-12 h-12 bg-brand/10 rounded-xl flex items-center justify-center mb-4 text-brand">
                <Zap className="w-6 h-6" />
              </div>
              <h3 className="text-lg font-semibold mb-2">Autonomous remediation</h3>
              <p className="text-muted-foreground text-sm">
                Turn insights into GitHub PRs with automated fixes and guardrails.
              </p>
            </div>
            <div className="p-6 glass-card border-border/70">
              <div className="w-12 h-12 bg-brand/10 rounded-xl flex items-center justify-center mb-4 text-brand">
                <Rocket className="w-6 h-6" />
              </div>
              <h3 className="text-lg font-semibold mb-2">Ready to launch fast</h3>
              <p className="text-muted-foreground text-sm">
                Start with one URL and get a full execution roadmap in minutes.
              </p>
            </div>
          </section>
        )}

        {!authLoading && user && (
          <section className="mt-16 space-y-6">
            <div className="flex justify-between items-center">
              <h2 className="text-2xl font-semibold tracking-tight">Recent audits</h2>
              {audits.length > 0 && (
                <Button
                  variant="ghost"
                  className="text-muted-foreground hover:text-foreground"
                  onClick={() => router.push(localePath('/audits'))}
                >
                  View all
                </Button>
              )}
            </div>

            {loading ? (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="glass-card h-48 animate-pulse" />
                ))}
              </div>
            ) : audits.length === 0 ? (
              <div className="text-center py-16 glass-card">
                <Globe className="w-12 h-12 text-muted-foreground/50 mx-auto mb-4" />
                <h3 className="text-xl font-medium text-muted-foreground mb-2">No audits yet</h3>
                <p className="text-muted-foreground/70 mb-4">
                  Enter a URL above to start your first audit.
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {audits.map((audit) => (
                  <div
                    key={audit.id}
                    onClick={() => router.push(localePath(`/audits/${audit.id}`))}
                    className="p-6 glass-card cursor-pointer group hover:-translate-y-1"
                  >
                    <div className="flex items-center justify-between mb-4">
                      <div className="p-2 bg-muted/50 rounded-lg">
                        <Globe className="w-5 h-5 text-brand" />
                      </div>
                      <Badge variant="outline" className={`
                        ${audit.status === 'completed' ? 'bg-emerald-500/10 text-emerald-600 border-emerald-500/20' :
                          audit.status === 'failed' ? 'bg-red-500/10 text-red-600 border-red-500/20' :
                            audit.status === 'running' ? 'bg-brand/10 text-brand border-brand/20' :
                              'bg-amber-500/10 text-amber-600 border-amber-500/20'}
                      `}>
                        {audit.status}
                      </Badge>
                    </div>

                    <h3 className="text-lg font-medium truncate mb-1 group-hover:text-brand transition-colors">
                      {audit.domain || (() => {
                        try {
                          return new URL(audit.url).hostname.replace('www.', '')
                        } catch {
                          return audit.url
                        }
                      })()}
                    </h3>
                    <p className="text-sm text-muted-foreground truncate mb-4">{audit.url}</p>

                    <div className="flex justify-between items-center pt-4 border-t border-border text-sm">
                      <span className="flex items-center gap-1 text-muted-foreground">
                        <Clock className="w-3 h-3" />
                        {new Date(audit.created_at).toLocaleDateString()}
                      </span>
                      {audit.status === 'completed' && audit.geo_score && (
                        <span className="text-emerald-600 font-medium">
                          GEO: {Math.round(audit.geo_score)}%
                        </span>
                      )}
                      <ArrowRight className="w-4 h-4 text-muted-foreground group-hover:text-foreground transition-colors" />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        )}
      </main>

      <footer className="border-t border-border mt-20 py-8">
        <div className="max-w-6xl mx-auto px-6 text-center text-muted-foreground text-sm">
          © 2026 LatentGEO.ai. Built for Nicolas Leiva.
        </div>
      </footer>
    </div>
  )
}
