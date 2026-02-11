"use client"

import { useState } from "react"
import { Header } from "@/components/header"
import { AdminGate } from "@/components/auth/AdminGate"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { API_URL } from "@/lib/api"
import { RefreshCw, RotateCcw } from "lucide-react"

export default function HubSpotRollbackPage() {
  const [changeId, setChangeId] = useState("")
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState<string>("")

  const rollback = async () => {
    const id = changeId.trim()
    if (!id) {
      setError("Please enter a change_id.")
      return
    }
    setError("")
    setLoading(true)
    setResult(null)
    try {
      const res = await fetch(`${API_URL}/api/hubspot/rollback/${encodeURIComponent(id)}`, {
        method: "POST",
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) {
        setError(data?.detail || data?.error || `Error ${res.status}`)
        return
      }
      setResult(data)
    } catch (e) {
      console.error(e)
      setError("Error calling HubSpot rollback.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Header />
      <AdminGate title="HubSpot Rollback">
        <main className="max-w-4xl mx-auto px-6 py-12">
          <div className="mb-8">
            <h1 className="text-3xl font-bold">HubSpot Rollback</h1>
            <p className="text-muted-foreground mt-1">
              Revert a change applied in HubSpot using its change_id
            </p>
          </div>

          <Card className="glass-card p-6">
            <div className="space-y-2">
              <Label>change_id</Label>
              <Input value={changeId} onChange={(e) => setChangeId(e.target.value)} placeholder="e.g. 123e4567..." />
            </div>

            <div className="flex gap-2 mt-4">
              <Button onClick={rollback} disabled={loading}>
                {loading ? <RefreshCw className="h-4 w-4 mr-2 animate-spin" /> : <RotateCcw className="h-4 w-4 mr-2" />}
                Rollback
              </Button>
            </div>

            {error && <div className="text-sm text-red-400 mt-4">{error}</div>}

            {result && (
              <pre className="mt-6 text-xs bg-muted/40 border border-border rounded-xl p-4 overflow-auto">
                {JSON.stringify(result, null, 2)}
              </pre>
            )}
          </Card>
        </main>
      </AdminGate>
    </div>
  )
}
