'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { Header } from '@/components/header'
import { Button } from '@/components/ui/button'
import { RefreshCw } from 'lucide-react'
import { api } from '@/lib/api'

export default function AuditsListPage() {
  const router = useRouter()
  const [audits, setAudits] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchAudits = async () => {
      try {
        const response = await fetch('http://localhost:8000/audits')
        const data = await response.json()
        setAudits(data)
      } catch (err) {
        console.error(err)
      } finally {
        setLoading(false)
      }
    }
    fetchAudits()
  }, [])

  if (loading) {
    return (
      <div className="flex min-h-screen flex-col">
        <Header />
        <main className="flex-1 flex items-center justify-center">
          <RefreshCw className="h-8 w-8 animate-spin" />
        </main>
      </div>
    )
  }

  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main className="flex-1 container mx-auto px-4 py-8">
        <h1 className="text-3xl font-bold mb-6">Auditorías</h1>
        <div className="grid gap-4">
          {audits.map((audit) => (
            <div
              key={audit.id}
              onClick={() => router.push(`/audits/${audit.id}`)}
              className="bg-white border-2 border-black rounded-lg p-6 cursor-pointer hover:bg-gray-50"
            >
              <div className="flex justify-between items-start">
                <div>
                  <h3 className="font-bold text-lg">#{audit.id} - {audit.url}</h3>
                  <p className="text-sm text-muted-foreground">{audit.domain}</p>
                </div>
                <span className={`px-3 py-1 rounded-full text-white text-sm ${
                  audit.status === 'completed' ? 'bg-green-500' : 'bg-blue-500'
                }`}>
                  {audit.status}
                </span>
              </div>
            </div>
          ))}
        </div>
      </main>
    </div>
  )
}
