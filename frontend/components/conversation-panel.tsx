'use client'

import { useEffect, useRef } from 'react'
import { User, Bot, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { AISearchBar } from '@/components/ai-search-bar'
import type { ConversationMessage } from '@/lib/types'
import { cn } from '@/lib/utils'

interface ConversationPanelProps {
  messages: ConversationMessage[]
  isLoading: boolean
  onSearch: (query: string) => void
}

export function ConversationPanel({ messages, isLoading, onSearch }: ConversationPanelProps) {
  const bottomRef = useRef<HTMLDivElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const container = containerRef.current
    if (!container) return
    const distanceFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight
    const isNearBottom = distanceFromBottom < 120
    if (isNearBottom) {
      container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' })
    }
  }, [messages])

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)]">
      <div ref={containerRef} className="flex-1 overflow-y-auto px-4 py-6">
        <div className="max-w-3xl mx-auto space-y-6">
          {messages.map((message) => (
            <div
              key={message.id}
              className={cn(
                'flex gap-4',
                message.role === 'user' ? 'justify-end' : 'justify-start'
              )}
            >
              {message.role === 'assistant' && (
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary flex items-center justify-center">
                  <Bot className="h-4 w-4 text-primary-foreground" />
                </div>
              )}

              <div
                className={cn(
                  'rounded-lg px-4 py-3 max-w-[80%]',
                  message.role === 'user'
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-secondary text-secondary-foreground border border-border'
                )}
              >
                <p className="text-sm leading-relaxed">{message.content}</p>

                {message.suggestions && message.suggestions.length > 0 && (
                  <div className="mt-4 flex flex-wrap gap-2">
                    {message.suggestions.map((suggestion, idx) => (
                      <Button
                        key={idx}
                        variant="outline"
                        size="sm"
                        onClick={() => onSearch(suggestion)}
                        className="text-xs border-border hover:bg-accent"
                      >
                        {suggestion}
                      </Button>
                    ))}
                  </div>
                )}
              </div>

              {message.role === 'user' && (
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-secondary border border-border flex items-center justify-center">
                  <User className="h-4 w-4 text-foreground" />
                </div>
              )}
            </div>
          ))}

          {isLoading && (
            <div className="flex gap-4 justify-start">
              <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary flex items-center justify-center">
                <Bot className="h-4 w-4 text-primary-foreground" />
              </div>
              <div className="rounded-lg px-4 py-3 bg-secondary border border-border">
                <Loader2 className="h-4 w-4 animate-spin text-foreground" />
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      </div>

      <div className="border-t border-border bg-background">
        <div className="max-w-3xl mx-auto px-4 py-4">
          <AISearchBar onSearch={onSearch} placeholder="Continue the conversation..." />
        </div>
      </div>
    </div>
  )
}
