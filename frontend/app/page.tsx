"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { NewAuditModal } from "@/components/new-audit-modal"
import { AuditsTable } from "@/components/audits-table"
import { useAudits } from "@/hooks/use-audits"
import { Plus, RefreshCw } from "lucide-react"
import { Skeleton } from "@/components/ui/skeleton"

export default function DashboardPage() {
  const [modalOpen, setModalOpen] = useState(false)
  const [isClient, setIsClient] = useState(false)
  const { audits, isLoading, refresh } = useAudits()

  useEffect(() => {
    setIsClient(true)
  }, [])

  return (
    <div className="min-h-screen bg-white">
      <div className="container mx-auto py-8 px-4 max-w-7xl">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-4xl font-bold tracking-tight text-black text-balance">SEO Audit Dashboard</h1>
            <p className="text-gray-600 mt-2">Monitor and manage your website audits in real-time</p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="icon" onClick={refresh} className="shrink-0 bg-transparent">
              <RefreshCw className="w-4 h-4" />
            </Button>
            <Button onClick={() => setModalOpen(true)} size="lg" className="shrink-0">
              <Plus className="w-5 h-5 mr-2" />
              New Audit
            </Button>
          </div>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Recent Audits</CardTitle>
            <CardDescription>Track the status and progress of your SEO audits</CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading || !isClient || audits.length === 0 ? (
              <div className="space-y-4">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="flex items-center gap-4">
                    <Skeleton className="h-12 w-full" />
                  </div>
                ))}
              </div>
            ) : (
              <AuditsTable audits={audits} />
            )}
          </CardContent>
        </Card>

        <NewAuditModal open={modalOpen} onOpenChange={setModalOpen} onSuccess={refresh} />
      </div>
    </div>
  )
}
