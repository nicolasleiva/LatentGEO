import type { Audit, CreateAuditRequest } from "./types"

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

export async function fetchAudits(): Promise<Audit[]> {
  const response = await fetch(`${API_BASE_URL}/audits`)
  if (!response.ok) {
    throw new Error("Failed to fetch audits")
  }
  return response.json()
}

export async function createAudit(data: CreateAuditRequest): Promise<Audit> {
  const response = await fetch(`${API_BASE_URL}/audits`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  })

  if (!response.ok) {
    throw new Error("Failed to create audit")
  }

  return response.json()
}

export async function fetchAudit(id: number): Promise<Audit> {
  const response = await fetch(`${API_BASE_URL}/audits/${id}`)
  if (!response.ok) {
    throw new Error("Failed to fetch audit")
  }
  return response.json()
}

export async function downloadPDF(id: number): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/audits/${id}/download-pdf`)
  if (!response.ok) {
    throw new Error("Failed to download PDF")
  }

  const blob = await response.blob()
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = `audit-${id}-report.pdf`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  window.URL.revokeObjectURL(url)
}
