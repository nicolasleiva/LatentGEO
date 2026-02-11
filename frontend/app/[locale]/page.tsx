'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useUser } from '@auth0/nextjs-auth0/client'
import { API_URL } from '@/lib/api'
import {
  Search,
  ArrowRight,
  Activity,
  Globe,
  Clock,
  Sparkles,
  Shield,
  Zap,
  Check,
  GitPullRequest,
  ScrollText,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Header } from '@/components/header'

interface Audit {
  id: number
  url: string
  domain: string
  status: string
  created_at: string
  geo_score?: number
}

export default function HomePage() {
  const router = useRouter()
  const { user, isLoading: authLoading } = useUser()
  const [url, setUrl] = useState('')
  const [audits, setAudits] = useState<Audit[]>([])
  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const backendUrl = API_URL

  useEffect(() => {
    if (user && !authLoading) {
      setLoading(true)
      const userEmailParam = user.email ? `?user_email=${encodeURIComponent(user.email)}` : ''
      fetch(`${backendUrl}/api/audits${userEmailParam}`)
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
        user_id: user.sub,
        user_email: user.email,
      }

      const res = await fetch(endpoint, {
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
          const redirectRes = await fetch(redirectUrl, {
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
            router.push(`/audits/${newAudit.id}`)
            return
          } else {
            throw new Error(`Error after redirect: ${redirectRes.status}`)
          }
        }
      }

      if (res.ok || res.status === 202) {
        const newAudit = await res.json()
        router.push(`/audits/${newAudit.id}`)
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

      <main className="max-w-6xl mx-auto px-6 py-12">
        <section className="grid gap-12 lg:grid-cols-[1.1fr_0.9fr] items-center">
          <div className="space-y-8">
            <div className="inline-flex items-center gap-2 px-4 py-2 bg-foreground/5 border border-foreground/10 rounded-full text-foreground/80 text-sm">
              <Sparkles className="w-4 h-4 text-brand" />
              The real growth hacking
            </div>

            <h1 className="text-5xl md:text-6xl lg:text-7xl font-semibold tracking-tight">
              Autonomous growth engineering powered by AI.
            </h1>

            <p className="text-lg text-muted-foreground max-w-2xl leading-relaxed">
              LatentGEO.ai detects friction, prioritizes impact, and automates execution so teams can
              ship measurable growth faster with no guesswork.
            </p>



            <form onSubmit={handleAudit} className="max-w-2xl relative">
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
          </div>

          <div className="space-y-6">
            <div className="glass-card p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm uppercase tracking-widest text-muted-foreground">Autonomous PRs</p>
                  <h3 className="text-2xl font-semibold mt-2">Fixes that ship themselves</h3>
                </div>
                <GitPullRequest className="w-10 h-10 text-brand" />
              </div>
              <p className="text-sm text-muted-foreground mt-4">
                Generate production-ready pull requests with code fixes, tests, and validation steps.
              </p>
            </div>
            <div className="glass-card p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm uppercase tracking-widest text-muted-foreground">Audit signal</p>
                  <h3 className="text-2xl font-semibold mt-2">URL-level intelligence</h3>
                </div>
                <ScrollText className="w-10 h-10 text-brand" />
              </div>
              <p className="text-sm text-muted-foreground mt-4">
                Measure GEO, AI visibility, and technical SEO health in a single unified audit.
              </p>
            </div>
            <div className="glass-card p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm uppercase tracking-widest text-muted-foreground">Secure by design</p>
                  <h3 className="text-2xl font-semibold mt-2">Enterprise-grade control</h3>
                </div>
                <Shield className="w-10 h-10 text-brand" />
              </div>
              <p className="text-sm text-muted-foreground mt-4">
                Scoped access, audit trails, and approvals keep every automated fix compliant.
              </p>
            </div>
          </div>
        </section>

        {!authLoading && !user && (
          <section className="mt-20 grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="p-6 glass-card">
              <div className="w-12 h-12 bg-brand/10 rounded-xl flex items-center justify-center mb-4">
                <Globe className="w-6 h-6 text-brand" />
              </div>
              <h3 className="text-lg font-semibold mb-2">Generative search coverage</h3>
              <p className="text-muted-foreground text-sm">
                Understand how your brand appears in AI answers and conversational search.
              </p>
            </div>
            <div className="p-6 glass-card">
              <div className="w-12 h-12 bg-brand/10 rounded-xl flex items-center justify-center mb-4">
                <Zap className="w-6 h-6 text-brand" />
              </div>
              <h3 className="text-lg font-semibold mb-2">Autonomous remediation</h3>
              <p className="text-muted-foreground text-sm">
                Turn insights into GitHub PRs with automated fixes and guardrails.
              </p>
            </div>
            <div className="p-6 glass-card">
              <div className="w-12 h-12 bg-brand/10 rounded-xl flex items-center justify-center mb-4">
                <Activity className="w-6 h-6 text-brand" />
              </div>
              <h3 className="text-lg font-semibold mb-2">Always-on readiness</h3>
              <p className="text-muted-foreground text-sm">
                Track progress over time with live audit status and performance signals.
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
                  onClick={() => router.push('/audits')}
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
                    onClick={() => router.push(`/audits/${audit.id}`)}
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
