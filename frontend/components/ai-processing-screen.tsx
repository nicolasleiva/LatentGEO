'use client'

import { useState, useEffect } from 'react'

interface AIProcessingScreenProps {
  isProcessing: boolean
}

const processingMessages = [
  'Initializing analysis engine',
  'Scanning your website',
  'Mapping technical signals',
  'Evaluating GEO readiness',
  'Running AI visibility checks',
  'Generating recommendations',
  'Preparing final report',
]

export function AIProcessingScreen({ isProcessing }: AIProcessingScreenProps) {
  const [currentMessageIndex, setCurrentMessageIndex] = useState(0)
  const [isVisible, setIsVisible] = useState(true)

  useEffect(() => {
    if (!isProcessing) return

    const interval = setInterval(() => {
      setIsVisible(false)

      setTimeout(() => {
        setCurrentMessageIndex((prev) =>
          prev >= processingMessages.length - 1 ? prev : prev + 1
        )
        setIsVisible(true)
      }, 250)
    }, 3200)

    return () => clearInterval(interval)
  }, [isProcessing])

  if (!isProcessing) return null

  return (
    <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-background/95 backdrop-blur-xl">
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-0 left-0 w-[520px] h-[520px] rounded-full bg-brand/10 blur-[120px]" />
        <div className="absolute bottom-0 right-0 w-[520px] h-[520px] rounded-full bg-foreground/5 blur-[140px]" />
      </div>

      <div className="relative z-10 flex flex-col items-center">
        <div className="relative mb-10">
          <div className="w-24 h-24 rounded-full border border-foreground/10" />
          <div className="absolute inset-0 animate-spin">
            <div className="w-24 h-24 rounded-full border border-transparent border-t-brand" />
          </div>
          <div className="absolute inset-4 rounded-full border border-foreground/10" />
          <div className="absolute inset-8 rounded-full bg-brand/15" />
        </div>

        <div className="h-8 flex items-center justify-center">
          <p
            className={`text-base font-medium text-foreground/80 transition-all duration-300 ${
              isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2'
            }`}
          >
            {processingMessages[currentMessageIndex]}
          </p>
        </div>

        <p className="mt-6 text-xs uppercase tracking-[0.4em] text-muted-foreground">
          LatentGEO.ai running
        </p>
      </div>
    </div>
  )
}
