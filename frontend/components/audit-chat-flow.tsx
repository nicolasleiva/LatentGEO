'use client'

import { useState, useEffect, useRef } from 'react'
import { Input } from '@/components/ui/input'
import { Send } from 'lucide-react'

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
  const [config, setConfig] = useState({ language: '', competitors: [] as string[], market: '' })
  const [step, setStep] = useState<'competitors' | 'market' | 'done'>('competitors')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    setConfig(prev => ({ ...prev, language: 'en' }))
    sendAIMessage("Hi! I'm your AI audit assistant. Would you like to add specific competitor URLs for comparison? You can type URLs separated by commas, or just say 'no' to skip.")
    setStep('competitors')
    inputRef.current?.focus()
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendAIMessage = (content: string) => {
    setIsTyping(true)
    const words = content.split(' ')
    let currentText = ''
    let wordIndex = 0

    const typingInterval = setInterval(() => {
      if (wordIndex < words.length) {
        currentText += (wordIndex > 0 ? ' ' : '') + words[wordIndex]
        setMessages(prev => {
          const newMessages = [...prev]
          if (newMessages[newMessages.length - 1]?.typing) {
            newMessages[newMessages.length - 1] = { role: 'assistant', content: currentText, typing: true }
          } else {
            newMessages.push({ role: 'assistant', content: currentText, typing: true })
          }
          return newMessages
        })
        wordIndex++
      } else {
        clearInterval(typingInterval)
        setMessages(prev => {
          const newMessages = [...prev]
          newMessages[newMessages.length - 1] = { role: 'assistant', content: currentText }
          return newMessages
        })
        setIsTyping(false)
      }
    }, 50)
  }

  const handleSend = async () => {
    if (!input.trim() || isTyping) return

    const userMessage = input.trim()
    setMessages(prev => [...prev, { role: 'user', content: userMessage }])
    setInput('')

    if (step === 'competitors') {
      if (userMessage.toLowerCase().includes('no') || userMessage.toLowerCase().includes('skip')) {
        setStep('market')
        await new Promise(resolve => setTimeout(resolve, 500))
        sendAIMessage("Understood. What about target markets? Would you like to specify countries or regions? (e.g., 'US', 'Latin America', 'Europe', or 'no')")
      } else {
        const urls = userMessage.split(',').map(u => {
          let url = u.trim()
          if (url && !url.startsWith('http')) {
            url = 'https://' + url
          }
          return url
        }).filter(u => u.includes('.'))
        setConfig(prev => ({ ...prev, competitors: urls }))
        setStep('market')
        await new Promise(resolve => setTimeout(resolve, 500))
        sendAIMessage(`Perfect! I've added ${urls.length} competitor(s). Now, what about target markets? Would you like to specify countries or regions? (e.g., 'US', 'Latin America', 'Europe', or 'no')`)
      }
    } else if (step === 'market') {
      const market = userMessage.toLowerCase().includes('no') ? '' : userMessage
      setConfig(prev => ({ ...prev, market }))
      setStep('done')
      await new Promise(resolve => setTimeout(resolve, 500))
      sendAIMessage("Excellent! I'm starting your comprehensive audit now. This will take a few minutes...")
      
      try {
        // Primero crear la auditoría
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
        const createResponse = await fetch(`${apiUrl}/api/audits`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            url: typeof auditId === 'string' ? auditId : '',
            language: config.language || 'en',
            competitors: config.competitors.length > 0 ? config.competitors : null,
            market: market || null
          })
        })
        const audit = await createResponse.json()
        
        setTimeout(() => {
          window.location.href = `/audits/${audit.id}`
        }, 2000)
      } catch (error) {
        console.error('Error:', error)
        onComplete()
      }
    }
  }

  return (
    <div className="flex flex-col h-[600px] max-w-3xl mx-auto bg-white border-2 border-black rounded-lg">
      {/* Chat header */}
      <div className="border-b-2 border-black p-4">
        <h2 className="font-bold text-lg">AI Audit Assistant</h2>
        <p className="text-sm text-gray-600">Powered by KIMI</p>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg, idx) => (
          <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[80%] rounded-lg p-3 ${
              msg.role === 'user'
                ? 'bg-black text-white'
                : 'bg-gray-100 text-black border border-gray-300'
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
        <div className="border-t-2 border-black p-4">
          <div className="flex gap-2">
            <Input
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSend()}
              placeholder="Type your response..."
              disabled={isTyping}
              className="flex-1"
            />
            <button
              onClick={handleSend}
              disabled={isTyping || !input.trim()}
              className="px-4 py-2 bg-black text-white rounded-lg hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Send className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
