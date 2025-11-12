"use client"

import { useState, useEffect, useCallback } from "react"
import { fetchAudits } from "@/lib/api"
import type { Audit } from "@/lib/types"

export function useAudits() {
  const [audits, setAudits] = useState<Audit[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadAudits = useCallback(async () => {
    try {
      const data = await fetchAudits()
      setAudits(data)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load audits")
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    loadAudits()

    // Polling every 3 seconds
    const interval = setInterval(() => {
      loadAudits()
    }, 3000)

    return () => clearInterval(interval)
  }, [loadAudits])

  return { audits, isLoading, error, refresh: loadAudits }
}
