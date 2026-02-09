"use client"

import { useMemo, useState } from "react"
import { Header } from "@/components/header"
import { AdminGate } from "@/components/auth/AdminGate"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { API_URL } from "@/lib/api"
import { Github, Loader2, RefreshCw } from "lucide-react"

export default function GitHubAdminPage() {
  const [connectionId, setConnectionId] = useState("")
  const [repoId, setRepoId] = useState("")
  const [auditId, setAuditId] = useState("")
  const [blogPaths, setBlogPaths] = useState("")
  const [competitorUrls, setCompetitorUrls] = useState("")
  const [fixesJson, setFixesJson] = useState("[]")
  const [loading, setLoading] = useState(false)
  const [output, setOutput] = useState<any>(null)
  const [error, setError] = useState<string>("")

  const parsedAuditId = useMemo(() => {
    const n = Number(auditId)
    return Number.isFinite(n) ? n : null
  }, [auditId])

  const run = async (label: string, fn: () => Promise<any>) => {
    setLoading(true)
    setError("")
    try {
      const data = await fn()
      setOutput({ action: label, data })
    } catch (e: any) {
      console.error(e)
      setError(e?.message || "Error ejecutando acción.")
      setOutput({ action: label, error: e?.message || String(e) })
    } finally {
      setLoading(false)
    }
  }

  const authorize = () => {
    window.location.href = `${API_URL}/api/github/oauth/authorize`
  }

  const parseBlogPaths = () =>
    blogPaths
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean)

  const parseCompetitors = () =>
    competitorUrls
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean)

  const parseFixes = () => {
    try {
      const parsed = JSON.parse(fixesJson)
      return Array.isArray(parsed) ? parsed : []
    } catch {
      return []
    }
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Header />
      <AdminGate title="GitHub Admin">
        <main className="max-w-6xl mx-auto px-6 py-12 space-y-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold flex items-center gap-3">
              <Github className="h-7 w-7" />
              GitHub Admin
            </h1>
            <p className="text-muted-foreground mt-1">
              Panel para ejecutar todas las funciones GitHub del backend
            </p>
          </div>
          <Button onClick={authorize} className="glass-button-primary">
            Connect / Login
          </Button>
        </div>

        <Card className="glass-card p-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label>connection_id</Label>
              <Input value={connectionId} onChange={(e) => setConnectionId(e.target.value)} placeholder="Ej: gh_conn_..." />
            </div>
            <div className="space-y-2">
              <Label>repo_id</Label>
              <Input value={repoId} onChange={(e) => setRepoId(e.target.value)} placeholder="Ej: gh_repo_..." />
            </div>
            <div className="space-y-2">
              <Label>audit_id</Label>
              <Input value={auditId} onChange={(e) => setAuditId(e.target.value)} placeholder="Ej: 123" inputMode="numeric" />
            </div>
          </div>
        </Card>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card className="glass-card p-6 space-y-3">
            <div className="text-lg font-semibold">Core</div>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                disabled={loading}
                onClick={() => run("GET /github/connections", async () => {
                  const res = await fetch(`${API_URL}/api/github/connections`)
                  if (!res.ok) throw new Error(`HTTP ${res.status}`)
                  return res.json()
                })}
              >
                {loading ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <RefreshCw className="h-4 w-4 mr-2" />}
                Connections
              </Button>
              <Button
                variant="outline"
                disabled={loading || !connectionId}
                onClick={() => run("POST /github/sync/{connection_id}", async () => {
                  const res = await fetch(`${API_URL}/api/github/sync/${encodeURIComponent(connectionId)}`, { method: "POST" })
                  if (!res.ok) throw new Error(`HTTP ${res.status}`)
                  return res.json()
                })}
              >
                Sync Repos
              </Button>
              <Button
                variant="outline"
                disabled={loading || !connectionId}
                onClick={() => run("GET /github/repos/{connection_id}", async () => {
                  const res = await fetch(`${API_URL}/api/github/repos/${encodeURIComponent(connectionId)}`)
                  if (!res.ok) throw new Error(`HTTP ${res.status}`)
                  return res.json()
                })}
              >
                List Repos
              </Button>
              <Button
                variant="outline"
                disabled={loading || !connectionId || !repoId}
                onClick={() => run("POST /github/analyze/{connection_id}/{repo_id}", async () => {
                  const res = await fetch(`${API_URL}/api/github/analyze/${encodeURIComponent(connectionId)}/${encodeURIComponent(repoId)}`, { method: "POST" })
                  if (!res.ok) throw new Error(`HTTP ${res.status}`)
                  return res.json()
                })}
              >
                Analyze Repo
              </Button>
              <Button
                variant="outline"
                disabled={loading || !repoId}
                onClick={() => run("GET /github/prs/{repo_id}", async () => {
                  const res = await fetch(`${API_URL}/api/github/prs/${encodeURIComponent(repoId)}`)
                  if (!res.ok) throw new Error(`HTTP ${res.status}`)
                  return res.json()
                })}
              >
                List PRs
              </Button>
            </div>
          </Card>

          <Card className="glass-card p-6 space-y-3">
            <div className="text-lg font-semibold">PR / Fixes</div>
            <div className="space-y-2">
              <Label>fixes (JSON array)</Label>
              <Textarea
                value={fixesJson}
                onChange={(e) => setFixesJson(e.target.value)}
                className="min-h-[140px] font-mono text-xs"
              />
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                disabled={loading || !connectionId || !repoId || !parsedAuditId}
                onClick={() => run("POST /github/create-pr", async () => {
                  const res = await fetch(`${API_URL}/api/github/create-pr`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                      connection_id: connectionId,
                      repo_id: repoId,
                      audit_id: parsedAuditId,
                      fixes: parseFixes(),
                    }),
                  })
                  const data = await res.json().catch(() => ({}))
                  if (!res.ok) throw new Error(data?.detail || `HTTP ${res.status}`)
                  return data
                })}
              >
                Create PR (manual fixes)
              </Button>
              <Button
                variant="outline"
                disabled={loading || !parsedAuditId}
                onClick={() => run("GET /github/audit-to-fixes/{audit_id}", async () => {
                  const res = await fetch(`${API_URL}/api/github/audit-to-fixes/${parsedAuditId}`)
                  const data = await res.json().catch(() => ({}))
                  if (!res.ok) throw new Error(data?.detail || `HTTP ${res.status}`)
                  return data
                })}
              >
                Audit → Fixes
              </Button>
              <Button
                disabled={loading || !connectionId || !repoId || !parsedAuditId}
                onClick={() => run("POST /github/create-auto-fix-pr/{connection}/{repo}", async () => {
                  const res = await fetch(`${API_URL}/api/github/create-auto-fix-pr/${encodeURIComponent(connectionId)}/${encodeURIComponent(repoId)}`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ audit_id: parsedAuditId }),
                  })
                  const data = await res.json().catch(() => ({}))
                  if (!res.ok) throw new Error(data?.detail || `HTTP ${res.status}`)
                  return data
                })}
              >
                Create Auto-Fix PR (from audit)
              </Button>
            </div>
          </Card>

          <Card className="glass-card p-6 space-y-3">
            <div className="text-lg font-semibold">Blogs (SEO)</div>
            <div className="space-y-2">
              <Label>blog_paths (one per line)</Label>
              <Textarea value={blogPaths} onChange={(e) => setBlogPaths(e.target.value)} className="min-h-[120px] font-mono text-xs" />
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                disabled={loading || !connectionId || !repoId}
                onClick={() => run("POST /github/audit-blogs/{connection}/{repo}", async () => {
                  const res = await fetch(`${API_URL}/api/github/audit-blogs/${encodeURIComponent(connectionId)}/${encodeURIComponent(repoId)}`, { method: "POST" })
                  const data = await res.json().catch(() => ({}))
                  if (!res.ok) throw new Error(data?.detail || `HTTP ${res.status}`)
                  return data
                })}
              >
                Audit Blogs
              </Button>
              <Button
                disabled={loading || !connectionId || !repoId || parseBlogPaths().length === 0}
                onClick={() => run("POST /github/create-blog-fixes-pr/{connection}/{repo}", async () => {
                  const res = await fetch(`${API_URL}/api/github/create-blog-fixes-pr/${encodeURIComponent(connectionId)}/${encodeURIComponent(repoId)}`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(parseBlogPaths()),
                  })
                  const data = await res.json().catch(() => ({}))
                  if (!res.ok) throw new Error(data?.detail || `HTTP ${res.status}`)
                  return data
                })}
              >
                Create Blog Fixes PR
              </Button>
            </div>
          </Card>

          <Card className="glass-card p-6 space-y-3">
            <div className="text-lg font-semibold">Blogs (SEO + GEO)</div>
            <div className="flex flex-wrap gap-2">
              <Button
                disabled={loading || !connectionId || !repoId}
                onClick={() => run("POST /github/audit-blogs-geo/{connection}/{repo}", async () => {
                  const res = await fetch(`${API_URL}/api/github/audit-blogs-geo/${encodeURIComponent(connectionId)}/${encodeURIComponent(repoId)}`, { method: "POST" })
                  const data = await res.json().catch(() => ({}))
                  if (!res.ok) throw new Error(data?.detail || `HTTP ${res.status}`)
                  return data
                })}
              >
                Audit Blogs GEO
              </Button>
              <Button
                disabled={loading || !connectionId || !repoId || parseBlogPaths().length === 0}
                onClick={() => run("POST /github/create-geo-fixes-pr/{connection}/{repo}", async () => {
                  const res = await fetch(`${API_URL}/api/github/create-geo-fixes-pr/${encodeURIComponent(connectionId)}/${encodeURIComponent(repoId)}`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ blog_paths: parseBlogPaths(), include_geo: true }),
                  })
                  const data = await res.json().catch(() => ({}))
                  if (!res.ok) throw new Error(data?.detail || `HTTP ${res.status}`)
                  return data
                })}
              >
                Create GEO Fixes PR
              </Button>
            </div>
          </Card>

          <Card className="glass-card p-6 space-y-3">
            <div className="text-lg font-semibold">GEO Score / Compare</div>
            <div className="space-y-2">
              <Label>competitor_urls (comma separated, optional)</Label>
              <Input value={competitorUrls} onChange={(e) => setCompetitorUrls(e.target.value)} placeholder="https://comp1.com, https://comp2.com" />
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                disabled={loading || !parsedAuditId}
                onClick={() => run("GET /github/geo-score/{audit_id}", async () => {
                  const res = await fetch(`${API_URL}/api/github/geo-score/${parsedAuditId}`)
                  const data = await res.json().catch(() => ({}))
                  if (!res.ok) throw new Error(data?.detail || `HTTP ${res.status}`)
                  return data
                })}
              >
                GEO Score
              </Button>
              <Button
                variant="outline"
                disabled={loading || !parsedAuditId}
                onClick={() => run("GET /github/geo-compare/{audit_id}", async () => {
                  const comps = parseCompetitors()
                  const qs = comps.map((u) => `competitor_urls=${encodeURIComponent(u)}`).join("&")
                  const url = qs ? `${API_URL}/api/github/geo-compare/${parsedAuditId}?${qs}` : `${API_URL}/api/github/geo-compare/${parsedAuditId}`
                  const res = await fetch(url)
                  const data = await res.json().catch(() => ({}))
                  if (!res.ok) throw new Error(data?.detail || `HTTP ${res.status}`)
                  return data
                })}
              >
                GEO Compare
              </Button>
            </div>
          </Card>
        </div>

        <Card className="glass-card p-6">
          <div className="flex items-center justify-between gap-4 mb-3">
            <div className="text-lg font-semibold">Output</div>
            {error && <div className="text-sm text-red-400">{error}</div>}
          </div>
          <pre className="text-xs bg-muted/40 border border-border rounded-xl p-4 overflow-auto max-h-[60vh]">
            {JSON.stringify(output, null, 2)}
          </pre>
        </Card>
        </main>
      </AdminGate>
    </div>
  )
}
