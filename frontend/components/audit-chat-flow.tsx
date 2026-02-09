'use client'

import { useState, useEffect, useRef } from 'react'
import { Input } from '@/components/ui/input'
import { Send, AlertCircle } from 'lucide-react'

interface AuditChatFlowProps {
  auditId: number | string
  onComplete: () => void
}

interface Message {
  role: 'user' | 'assistant'
  content: string
  typing?: boolean
}

export function AuditChatFlow({ auditId, onComplete }: AuditChatFlowProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isTyping, setIsTyping] = useState(false)
  const [config, setConfig] = useState({ competitors: [] as string[], market: '' })
  const [step, setStep] = useState<'competitors' | 'market' | 'done'>('competitors')
  const [error, setError] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const hasInitialized = useRef(false)

  useEffect(() => {
    // Prevenir doble ejecución en React Strict Mode
    if (hasInitialized.current) return
    hasInitialized.current = true
    
    sendAIMessage("Hello. I'm your AI audit assistant. Would you like to add specific competitor URLs for comparison? You can type URLs separated by commas, or just say 'no' to skip.")
    setStep('competitors')
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendAIMessage = (content: string) => {
    setIsTyping(true)
    // Mostrar mensaje inmediatamente con typing indicator
    setMessages(prev => [...prev, { role: 'assistant', content, typing: true }])
    
    // Remover typing indicator después de 300ms (mucho más rápido que antes)
    setTimeout(() => {
      setMessages(prev => {
        const newMessages = [...prev]
        const lastMsg = newMessages[newMessages.length - 1]
        if (lastMsg?.typing) {
          lastMsg.typing = false
        }
        return newMessages
      })
      setIsTyping(false)
    }, 300)
  }

  const handleSend = async () => {
    if (!input.trim() || isTyping) return

    const userMessage = input.trim()
    setMessages(prev => [...prev, { role: 'user', content: userMessage }])
    setInput('')

    if (step === 'competitors') {
      if (userMessage.toLowerCase().includes('no') || userMessage.toLowerCase().includes('skip')) {
        setStep('market')
        sendAIMessage("Understood. What about target markets? Would you like to specify countries or regions? (e.g., 'US', 'Latin America', 'Europe', or 'no')")
      } else {
        const urls = userMessage.split(',').map(u => {
          let url = u.trim()
          if (url && !url.startsWith('http')) {
            url = 'https://' + url
          }
          return url
        }).filter(u => u && (u.includes('.') || u.includes('localhost') || u.includes('127.0.0.1')))
        setConfig(prev => ({ ...prev, competitors: urls }))
        setStep('market')
        sendAIMessage(`Acknowledged. I've added ${urls.length} competitor(s). Now, what about target markets? Would you like to specify countries or regions? (e.g., 'US', 'Latin America', 'Europe', or 'no')`)
      }
    } else if (step === 'market') {
      const market = userMessage.toLowerCase().includes('no') ? '' : userMessage
      setConfig(prev => ({ ...prev, market }))
      setStep('done')
      sendAIMessage("Confirmed. I am initializing your comprehensive audit now. This process will take a few minutes.")

      try {
        // Configurar la auditoría existente
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

        const isValidId = (id: number | string): boolean => {
          if (typeof id === 'number') return !isNaN(id) && id > 0
          if (typeof id === 'string') return /^\d+$/.test(id) && parseInt(id, 10) > 0
          return false
        }

        if (auditId && isValidId(auditId)) {
          await fetch(`${apiUrl}/api/audits/chat/config`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
             body: JSON.stringify({
               audit_id: Number(auditId),
               language: 'en',
               competitors: config.competitors.length > 0 ? config.competitors : null,
               market: market || null
             })
          })
          // El backend inicia el pipeline automáticamente
          onComplete()
        } else {
          // Fallback: Crear nueva auditoría si no tenemos ID válido (comportamiento legacy)
          const createResponse = await fetch(`${apiUrl}/api/audits`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
             body: JSON.stringify({
               url: typeof auditId === 'string' ? auditId : '',
               language: 'en',
               competitors: config.competitors.length > 0 ? config.competitors : null,
               market: market || null
             })
          })
          const audit = await createResponse.json()
          window.location.href = `/audits/${audit.id}`
        }
      } catch (error) {
        console.error('Error:', error)
        onComplete()
      }
    }
  }

  return (
    <div className="flex flex-col h-[600px] max-w-3xl mx-auto bg-card border border-border rounded-xl shadow-sm">
      {/* Chat header */}
      <div className="border-b border-border p-4">
        <h2 className="font-medium text-lg">AI Audit Assistant</h2>
        <p className="text-sm text-muted-foreground">Powered by KIMI</p>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg, idx) => (
          <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[80%] rounded-lg p-3 ${msg.role === 'user'
              ? 'bg-primary text-primary-foreground'
              : 'bg-secondary text-secondary-foreground border border-border'
              }`}>
              <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
              {msg.typing && (
                <span className="inline-block w-1 h-4 bg-current ml-1 animate-pulse" />
              )}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      {step !== 'done' && (
        <div className="border-t border-border p-4">
          <div className="flex gap-2">
             <Input
               value={input}
              onChange={(e) => setInput(e.target.value)}
               onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              placeholder="Type your response..."
              disabled={isTyping}
              className="flex-1"
            />
            <button
              onClick={handleSend}
              disabled={isTyping || !input.trim()}
              className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <Send className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
