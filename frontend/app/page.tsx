'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Header } from '@/components/header'
import { AISearchBar } from '@/components/ai-search-bar'
import { ConversationPanel } from '@/components/conversation-panel'
import { AuditChatFlow } from '@/components/audit-chat-flow'
import { api } from '@/lib/api'
import type { ConversationMessage } from '@/lib/types'

export default function HomePage() {
  const [messages, setMessages] = useState<ConversationMessage[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [showChat, setShowChat] = useState(false)
  const [currentAuditId, setCurrentAuditId] = useState<number | null>(null)
  const router = useRouter()

  const handleSearch = async (query: string) => {
    // Detectar si es una URL para iniciar auditoría
    const urlPattern = /https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)/
    const isUrl = urlPattern.test(query)

    if (isUrl) {
      setIsLoading(true)
      try {
        // Solo guardar URL, NO crear auditoría todavía
        setCurrentAuditId(query as any)
        setShowChat(true)
      } catch (error) {
        console.error('Error:', error)
      } finally {
        setIsLoading(false)
      }
      return
    }

    // Flujo normal de conversación
    const userMessage: ConversationMessage = {
      id: `msg_${Date.now()}`,
      role: 'user',
      content: query,
      timestamp: new Date().toISOString()
    }

    setMessages(prev => [...prev, userMessage])
    setIsLoading(true)

    try {
      const response = await api.searchAI(query)
      
      const assistantMessage: ConversationMessage = {
        id: `msg_${Date.now() + 1}`,
        role: 'assistant',
        content: response.response,
        timestamp: new Date().toISOString(),
        suggestions: response.suggestions
      }

      setMessages(prev => [...prev, assistantMessage])
      
      if (response.audit_started && response.audit_id) {
        setTimeout(() => {
          router.push(`/audits/${response.audit_id}`)
        }, 2000)
      }
    } catch (error) {
      console.error('[v0] Search error:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleChatComplete = () => {
    // No hace nada, el chat maneja la redirección
  }

  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      
      <main className="flex-1">
        {showChat && currentAuditId ? (
          <div className="flex flex-col items-center justify-center min-h-[calc(100vh-4rem)] px-4 py-12">
            <AuditChatFlow auditId={currentAuditId} onComplete={handleChatComplete} />
          </div>
        ) : messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center min-h-[calc(100vh-4rem)] px-4 py-12">
            <div className="w-full max-w-3xl space-y-8 text-center">
              <div className="space-y-4">
                <h1 className="text-5xl font-bold tracking-tight text-balance">
                  AI-Powered SEO & GEO Auditing
                </h1>
                <p className="text-xl text-muted-foreground text-balance">
                  {'Discover issues, get AI recommendations, and optimize your site\'s performance with comprehensive audits'}
                </p>
              </div>

              <AISearchBar onSearch={handleSearch} />

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-8">
                <div className="p-6 text-left rounded-lg border-2 border-black bg-white">
                  <h3 className="font-semibold mb-2 text-foreground">Full Site Audit</h3>
                  <p className="text-sm text-muted-foreground">Comprehensive analysis of all pages</p>
                </div>
                <div className="p-6 text-left rounded-lg border-2 border-black bg-white">
                  <h3 className="font-semibold mb-2 text-foreground">Competitor Analysis</h3>
                  <p className="text-sm text-muted-foreground">See how you stack up against rivals</p>
                </div>
                <div className="p-6 text-left rounded-lg border-2 border-black bg-white">
                  <h3 className="font-semibold mb-2 text-foreground">E-E-A-T Analysis</h3>
                  <p className="text-sm text-muted-foreground">Evaluate expertise and trust signals</p>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <ConversationPanel messages={messages} isLoading={isLoading} onSearch={handleSearch} />
        )}
      </main>
    </div>
  )
}
