'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useUser } from '@auth0/nextjs-auth0/client'
import { Search, ArrowRight, Activity, Globe, Clock, Sparkles, Shield, Zap } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { AuthButtons } from '@/components/auth/AuthButtons'
import { ThemeToggle } from '@/components/theme-toggle'

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

  const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'

  // Solo cargar auditorías si el usuario está logueado
  useEffect(() => {
    if (user && !authLoading) {
      setLoading(true)
      // Filtrar auditorías por email del usuario
      const userEmailParam = user.email ? `?user_email=${encodeURIComponent(user.email)}` : ''
      fetch(`${backendUrl}/api/audits${userEmailParam}`)
        .then(res => res.json())
        .then(data => {
          // Ordenar por fecha más reciente
          const sorted = Array.isArray(data)
            ? data.sort((a: Audit, b: Audit) =>
              new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
            ).slice(0, 6) // Solo mostrar las últimas 6
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
      setError('Por favor, ingresa una URL válida')
      return
    }

    // Validar formato de URL básico
    try {
      new URL(url)
    } catch {
      setError('Por favor, ingresa una URL válida (ej: https://example.com)')
      return
    }

    // Si no está logueado, redirigir a login
    if (!user) {
      // Guardar URL en sessionStorage para usar después del login
      sessionStorage.setItem('pendingAuditUrl', url)
      window.location.href = '/auth/login'
      return
    }

    setSubmitting(true)
    try {
      // Asegurar que la URL tenga el formato correcto
      const endpoint = `${backendUrl}/api/audits/`.replace(/\/+$/, '/') // Asegurar un solo trailing slash
      const requestBody = {
        url: url.trim(),
        user_id: user.sub,  // Auth0 user ID
        user_email: user.email,
        // Don't provide config - let chat flow handle it
      }

      if (process.env.NODE_ENV === 'development') {
        console.log('Creating audit:', { endpoint, body: requestBody, backendUrl })
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

      if (process.env.NODE_ENV === 'development') {
        console.log('Response status:', res.status, res.statusText)
      }

      // Manejar redirecciones 307 manualmente
      if (res.status === 307 || res.status === 308) {
        const location = res.headers.get('Location')
        if (location) {
          if (process.env.NODE_ENV === 'development') {
            console.log('Following redirect to:', location)
          }
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
            if (process.env.NODE_ENV === 'development') {
              console.log('Audit created successfully:', newAudit)
            }
            router.push(`/audits/${newAudit.id}`)
            return
          } else {
            throw new Error(`Error después de redirección: ${redirectRes.status}`)
          }
        }
      }

      if (res.ok || res.status === 202) {
        const newAudit = await res.json()
        if (process.env.NODE_ENV === 'development') {
          console.log('Audit created successfully:', newAudit)
        }
        router.push(`/audits/${newAudit.id}`)
      } else {
        let errorText = 'Error desconocido'
        try {
          const errorData = await res.text()
          errorText = errorData || `Error ${res.status}: ${res.statusText}`
        } catch {
          errorText = `Error ${res.status}: ${res.statusText}`
        }
        console.error('Error creating audit:', { status: res.status, statusText: res.statusText, errorText })
        setError(`Error al crear la auditoría (${res.status}): ${errorText}`)
        setSubmitting(false)
      }
    } catch (error: any) {
      console.error('Error creating audit:', error)
      const errorMessage = error.message || 'Por favor, verifica que el servidor esté funcionando.'
      setError(`Error de conexión: ${errorMessage}`)
      setSubmitting(false)
    }
  }

  // Recuperar URL pendiente después del login
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
      {/* Navbar */}
      <nav className="sticky top-0 z-50 backdrop-blur-xl bg-background/80 border-b border-border">
        <div className="max-w-7xl mx-auto px-6 py-4 flex justify-between items-center">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl flex items-center justify-center shadow-lg shadow-blue-500/20">
              <Activity className="w-5 h-5 text-white" />
            </div>
            <span className="font-bold text-xl tracking-tight">Auditor GEO</span>
          </div>
          <div className="flex items-center gap-4">
            <a href="/docs" className="text-muted-foreground hover:text-foreground hover:bg-muted hidden md:flex px-4 py-2 rounded-lg transition-colors">
              Docs
            </a>
            <a href="/pricing" className="text-muted-foreground hover:text-foreground hover:bg-muted hidden md:flex px-4 py-2 rounded-lg transition-colors">
              Pricing
            </a>
            <ThemeToggle />
            <AuthButtons />
          </div>
        </div>
      </nav>

      <main className="max-w-6xl mx-auto px-6 py-12">
        {/* Hero Section */}
        <div className="text-center mb-16 space-y-8">
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-blue-500/10 border border-blue-500/20 rounded-full text-blue-400 text-sm mb-4">
            <Sparkles className="w-4 h-4" />
            Powered by AI
          </div>

          <h1 className="text-5xl md:text-7xl font-bold tracking-tighter">
            <span className="text-foreground">
              Audit your presence
            </span>
            <br />
            <span className="bg-clip-text text-transparent bg-gradient-to-r from-blue-500 to-purple-500">
              in the AI era.
            </span>
          </h1>

          <p className="text-xl text-muted-foreground max-w-2xl mx-auto font-light leading-relaxed">
            Understand how your brand appears in ChatGPT, Perplexity, and generative search.
            Get actionable insights to improve your GEO visibility.
          </p>

          {/* Search Bar */}
          <form onSubmit={handleAudit} className="max-w-2xl mx-auto relative group mt-8">
            <div className="absolute inset-0 bg-gradient-to-r from-blue-500/30 to-purple-500/30 rounded-2xl blur-xl opacity-0 group-hover:opacity-100 transition duration-500" />
            <div className="relative flex flex-col gap-2">
              <div className="relative flex items-center glass-panel backdrop-blur-xl border border-border rounded-2xl p-2 shadow-2xl">
                <Search className="w-5 h-5 text-muted-foreground ml-4" />
                <input
                  type="url"
                  placeholder="Enter your website URL (e.g., https://example.com)"
                  className="flex-1 bg-transparent border-none text-foreground placeholder:text-muted-foreground focus:ring-0 px-4 py-4 outline-none text-lg"
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
                  className="bg-gradient-to-r from-blue-500 to-purple-500 text-white px-8 py-4 rounded-xl font-semibold hover:opacity-90 transition-all active:scale-95 flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-blue-500/25"
                  onClick={(e) => {
                    e.preventDefault()
                    handleAudit(e as any)
                  }}
                >
                  {submitting ? (
                    <>
                      <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      Analyzing...
                    </>
                  ) : (
                    <>
                      Analyze <ArrowRight className="w-5 h-5" />
                    </>
                  )}
                </button>
              </div>
              {error && (
                <div className="text-red-500 text-sm px-4 py-2 bg-red-500/10 border border-red-500/20 rounded-lg">
                  {error}
                </div>
              )}
            </div>
          </form>

          {/* Login prompt for non-authenticated users */}
          {!authLoading && !user && (
            <p className="text-muted-foreground text-sm">
              <a href="/auth/login" className="text-blue-500 hover:text-blue-600 underline">Sign in</a>
              {' '}to save your audits and track progress over time.
            </p>
          )}
        </div>

        {/* Features for non-authenticated users */}
        {!authLoading && !user && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-16">
            <div className="p-6 glass-card backdrop-blur-xl border border-border rounded-2xl">
              <div className="w-12 h-12 bg-blue-500/10 rounded-xl flex items-center justify-center mb-4">
                <Globe className="w-6 h-6 text-blue-500" />
              </div>
              <h3 className="text-lg font-semibold mb-2">GEO Analysis</h3>
              <p className="text-muted-foreground text-sm">
                Analyze how your website appears in AI-powered search engines and chatbots.
              </p>
            </div>
            <div className="p-6 glass-card backdrop-blur-xl border border-border rounded-2xl">
              <div className="w-12 h-12 bg-purple-500/10 rounded-xl flex items-center justify-center mb-4">
                <Zap className="w-6 h-6 text-purple-500" />
              </div>
              <h3 className="text-lg font-semibold mb-2">Auto-Fix with AI</h3>
              <p className="text-muted-foreground text-sm">
                Get AI-powered suggestions and automatically fix SEO issues in your codebase.
              </p>
            </div>
            <div className="p-6 glass-card backdrop-blur-xl border border-border rounded-2xl">
              <div className="w-12 h-12 bg-green-500/10 rounded-xl flex items-center justify-center mb-4">
                <Shield className="w-6 h-6 text-green-500" />
              </div>
              <h3 className="text-lg font-semibold mb-2">Competitor Intel</h3>
              <p className="text-muted-foreground text-sm">
                Compare your GEO score with competitors and identify opportunities.
              </p>
            </div>
          </div>
        )}

        {/* Recent Audits - Only for authenticated users */}
        {!authLoading && user && (
          <div className="space-y-6">
            <div className="flex justify-between items-center">
              <h2 className="text-2xl font-semibold tracking-tight">Your Recent Audits</h2>
              {audits.length > 0 && (
                <Button
                  variant="ghost"
                  className="text-muted-foreground hover:text-foreground"
                  onClick={() => router.push('/audits')}
                >
                  View All
                </Button>
              )}
            </div>

            {loading ? (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="glass-card border border-border rounded-2xl h-48 animate-pulse" />
                ))}
              </div>
            ) : audits.length === 0 ? (
              <div className="text-center py-16 glass-card border border-border rounded-2xl">
                <Globe className="w-12 h-12 text-muted-foreground/50 mx-auto mb-4" />
                <h3 className="text-xl font-medium text-muted-foreground mb-2">No audits yet</h3>
                <p className="text-muted-foreground/70 mb-4">
                  Enter a URL above to start your first GEO audit.
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {audits.map((audit) => (
                  <div
                    key={audit.id}
                    onClick={() => router.push(`/audits/${audit.id}`)}
                    className="p-6 glass-card backdrop-blur-xl border border-border rounded-2xl cursor-pointer group hover:bg-muted/50 hover:border-border/80 transition-all"
                  >
                    <div className="flex items-center justify-between mb-4">
                      <div className="p-2 bg-muted/50 rounded-lg">
                        <Globe className="w-5 h-5 text-blue-500" />
                      </div>
                      <Badge variant="outline" className={`
                        ${audit.status === 'completed' ? 'bg-green-500/10 text-green-400 border-green-500/20' :
                          audit.status === 'failed' ? 'bg-red-500/10 text-red-400 border-red-500/20' :
                            audit.status === 'running' ? 'bg-blue-500/10 text-blue-400 border-blue-500/20' :
                              'bg-yellow-500/10 text-yellow-400 border-yellow-500/20'}
                      `}>
                        {audit.status}
                      </Badge>
                    </div>

                    <h3 className="text-lg font-medium truncate mb-1 group-hover:text-blue-500 transition-colors">
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
                        <span className="text-green-500 font-medium">
                          GEO: {Math.round(audit.geo_score)}%
                        </span>
                      )}
                      <ArrowRight className="w-4 h-4 text-muted-foreground group-hover:text-foreground transition-colors" />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-border mt-20 py-8">
        <div className="max-w-6xl mx-auto px-6 text-center text-muted-foreground text-sm">
          © 2024 Auditor GEO. Built for the AI-first web.
        </div>
      </footer>
    </div>
  )
}
