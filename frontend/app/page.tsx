'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Search, ArrowRight, Activity, Globe, Clock, Zap, BarChart2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'

export default function Dashboard() {
  const router = useRouter()
  const [url, setUrl] = useState('')
  const [audits, setAudits] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

  useEffect(() => {
    fetch(`${backendUrl}/api/audits`)
      .then(res => res.json())
      .then(data => {
        setAudits(data)
        setLoading(false)
      })
      .catch(err => {
        console.error(err)
        setLoading(false)
      })
  }, [backendUrl])

  const handleAudit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!url) return

    try {
      const res = await fetch(`${backendUrl}/api/audits`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url })
      })

      if (res.ok) {
        const newAudit = await res.json()
        router.push(`/audits/${newAudit.id}`)
      }
    } catch (error) {
      console.error('Error creating audit:', error)
    }
  }

  return (
    <div className="min-h-screen text-white p-8">
      {/* Navbar Minimalista */}
      <nav className="flex justify-between items-center mb-16 max-w-7xl mx-auto">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-white rounded-lg flex items-center justify-center">
            <Activity className="w-5 h-5 text-black" />
          </div>
          <span className="font-semibold text-xl tracking-tight">Auditor GEO</span>
        </div>
        <div className="flex gap-4">
          <Button variant="ghost" className="text-white/70 hover:text-white hover:bg-white/10">Docs</Button>
          <Button variant="ghost" className="text-white/70 hover:text-white hover:bg-white/10">Support</Button>
        </div>
      </nav>

      <main className="max-w-5xl mx-auto">
        {/* Hero Section */}
        <div className="text-center mb-20 space-y-6">
          <h1 className="text-6xl md:text-7xl font-bold tracking-tighter bg-clip-text text-transparent bg-gradient-to-b from-white to-white/50 pb-4">
            Audit your presence.
          </h1>
          <p className="text-xl text-white/60 max-w-2xl mx-auto font-light">
            Advanced GEO analysis powered by AI. Understand how your brand appears in the age of generative search.
          </p>

          {/* Search Bar */}
          <form onSubmit={handleAudit} className="max-w-xl mx-auto relative group">
            <div className="absolute inset-0 bg-gradient-to-r from-blue-500 to-purple-500 rounded-2xl blur opacity-20 group-hover:opacity-40 transition duration-500"></div>
            <div className="relative flex items-center glass rounded-2xl p-2">
              <Search className="w-5 h-5 text-white/40 ml-3" />
              <input
                type="url"
                placeholder="Enter domain (e.g., apple.com)"
                className="flex-1 bg-transparent border-none text-white placeholder:text-white/30 focus:ring-0 px-4 py-3 outline-none"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                required
              />
              <button
                type="submit"
                className="bg-white text-black px-6 py-3 rounded-xl font-medium hover:bg-white/90 transition-all active:scale-95 flex items-center gap-2"
              >
                Analyze <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </form>
        </div>

        {/* Recent Audits Grid */}
        <div className="space-y-6">
          <div className="flex justify-between items-end px-2">
            <h2 className="text-2xl font-semibold tracking-tight">Recent Audits</h2>
            <Button variant="link" className="text-white/50 hover:text-white">View All</Button>
          </div>

          {loading ? (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {[1, 2, 3].map((i) => (
                <div key={i} className="glass rounded-2xl h-48 animate-pulse"></div>
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {audits.map((audit) => (
                <div
                  key={audit.id}
                  onClick={() => router.push(`/audits/${audit.id}`)}
                  className="glass-card p-6 cursor-pointer group relative overflow-hidden"
                >
                  <div className="absolute top-0 right-0 p-4 opacity-0 group-hover:opacity-100 transition-opacity">
                    <ArrowRight className="w-5 h-5 text-white/50" />
                  </div>

                  <div className="flex flex-col h-full justify-between">
                    <div>
                      <div className="flex items-center gap-3 mb-4">
                        <div className="p-2 bg-white/5 rounded-lg">
                          <Globe className="w-5 h-5 text-blue-400" />
                        </div>
                        <Badge variant="outline" className={`
                          ${audit.status === 'completed' ? 'bg-green-500/10 text-green-400 border-green-500/20' :
                            audit.status === 'failed' ? 'bg-red-500/10 text-red-400 border-red-500/20' :
                              'bg-yellow-500/10 text-yellow-400 border-yellow-500/20'}
                          backdrop-blur-md border
                        `}>
                          {audit.status}
                        </Badge>
                      </div>
                      <h3 className="text-xl font-medium truncate mb-1">
                        {audit.domain || new URL(audit.url).hostname.replace('www.', '')}
                      </h3>
                      <p className="text-sm text-white/40 truncate">{audit.url}</p>
                    </div>

                    <div className="mt-6 pt-6 border-t border-white/5 flex justify-between items-center text-sm text-white/40">
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {new Date(audit.created_at).toLocaleDateString()}
                      </span>
                      {audit.status === 'completed' && (
                        <span className="flex items-center gap-1 text-white/60">
                          View Report
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
