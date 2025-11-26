'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { RefreshCw } from 'lucide-react'

export default function AuditsListPage() {
  const router = useRouter()
  const [audits, setAudits] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

  useEffect(() => {
    const fetchAudits = async () => {
      try {
        const response = await fetch(`${backendUrl}/api/audits`)
        const data = await response.json()
        setAudits(data)
      } catch (err) {
        console.error(err)
      } finally {
        setLoading(false)
      }
    }
    fetchAudits()
  }, [backendUrl])

  if (loading) {
    return (
      <div className="flex min-h-screen flex-col">
        <main className="flex-1 flex items-center justify-center">
          <RefreshCw className="h-8 w-8 animate-spin" />
        </main>
      </div>
    )
  }

  return (
    <div className="flex min-h-screen flex-col">
      <main className="flex-1 container mx-auto px-4 py-8 max-w-5xl">
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-2xl font-medium tracking-tight">Audit History</h1>
          <Button variant="outline" size="sm" onClick={() => window.location.reload()}>
            <RefreshCw className="h-4 w-4 mr-2" /> Refresh
          </Button>
        </div>

        <div className="grid gap-4">
          {audits.map((audit) => (
            <div
              key={audit.id}
              onClick={() => router.push(`/audits/${audit.id}`)}
              className="group bg-card border border-border rounded-xl p-6 cursor-pointer hover:bg-accent/50 transition-all duration-300"
            >
              <div className="flex justify-between items-center">
                <div className="flex items-center gap-4">
                  <div className="h-10 w-10 rounded-full bg-secondary flex items-center justify-center text-xs font-medium text-secondary-foreground">
                    #{audit.id}
                  </div>
                  <div>
                    <h3 className="font-medium text-base group-hover:text-primary transition-colors">{audit.url}</h3>
                    <p className="text-xs text-muted-foreground font-mono mt-1">{new Date(audit.created_at).toLocaleDateString()}</p>
                  </div>
                </div>
                <span className={`px-3 py-1 rounded-full text-xs font-medium border ${audit.status === 'completed'
                  ? 'bg-primary text-primary-foreground border-primary'
                  : 'bg-secondary text-secondary-foreground border-border'
                  }`}>
                  {audit.status.toUpperCase()}
                </span>
              </div>
            </div>
          ))}

          {audits.length === 0 && !loading && (
            <div className="text-center py-12 text-muted-foreground">
              No audits found. Start a new one from the home page.
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
