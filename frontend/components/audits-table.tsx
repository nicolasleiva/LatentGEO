"use client"

import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Button } from "@/components/ui/button"
import { AuditStatusBadge } from "./audit-status-badge"
import { ProgressBar } from "./progress-bar"
import type { Audit } from "@/lib/types"
import { Download, AlertCircle, Loader2 } from "lucide-react"
import { downloadPDF } from "@/lib/api"
import { useState } from "react"
import { useToast } from "@/hooks/use-toast"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"

interface AuditsTableProps {
  audits: Audit[]
}

export function AuditsTable({ audits }: AuditsTableProps) {
  const [downloadingIds, setDownloadingIds] = useState<Set<number>>(new Set())
  const { toast } = useToast()

  const handleDownload = async (id: number) => {
    setDownloadingIds((prev) => new Set(prev).add(id))

    try {
      await downloadPDF(id)
      toast({
        title: "Download Started",
        description: "Your PDF report is being downloaded.",
      })
    } catch (error) {
      toast({
        title: "Download Failed",
        description: error instanceof Error ? error.message : "Failed to download PDF",
        variant: "destructive",
      })
    } finally {
      setDownloadingIds((prev) => {
        const next = new Set(prev)
        next.delete(id)
        return next
      })
    }
  }

  const formatDate = (dateString: string) => {
    const date = new Date(dateString)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMs / 3600000)
    const diffDays = Math.floor(diffMs / 86400000)

    if (diffMins < 1) return "Just now"
    if (diffMins < 60) return `${diffMins}m ago`
    if (diffHours < 24) return `${diffHours}h ago`
    if (diffDays < 7) return `${diffDays}d ago`

    return date.toLocaleDateString()
  }

  if (audits.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <div className="w-12 h-12 rounded-full bg-gray-100 flex items-center justify-center mb-4">
          <AlertCircle className="w-6 h-6 text-gray-500" />
        </div>
        <h3 className="text-lg font-semibold mb-1 text-black">No audits yet</h3>
        <p className="text-sm text-gray-600">Launch your first audit to get started</p>
      </div>
    )
  }

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent bg-gray-50">
            <TableHead className="w-[30%] text-black font-semibold">URL</TableHead>
            <TableHead className="w-[15%] text-black font-semibold">Status</TableHead>
            <TableHead className="w-[20%] text-black font-semibold">Progress</TableHead>
            <TableHead className="w-[15%] text-black font-semibold">Created</TableHead>
            <TableHead className="w-[20%] text-right text-black font-semibold">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {audits.map((audit) => (
            <TableRow key={audit.id} className="hover:bg-gray-50">
              <TableCell className="font-mono text-sm text-black">
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <div className="truncate max-w-[300px]">{audit.url}</div>
                    </TooltipTrigger>
                    <TooltipContent>
                      <p>{audit.url}</p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </TableCell>
              <TableCell>
                <AuditStatusBadge status={audit.status} />
              </TableCell>
              <TableCell>
                {audit.status === "RUNNING" ? (
                  <div className="space-y-1">
                    <ProgressBar value={audit.progress} />
                    <span className="text-xs text-gray-600">{audit.progress}%</span>
                  </div>
                ) : (
                  <span className="text-sm text-gray-400">—</span>
                )}
              </TableCell>
              <TableCell className="text-sm text-gray-600">{formatDate(audit.created_at)}</TableCell>
              <TableCell className="text-right">
                {audit.status === "COMPLETED" && (
                  <>
                    {audit.report_pdf_path ? (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleDownload(audit.id)}
                        disabled={downloadingIds.has(audit.id)}
                        className="border-green-600 text-green-700 hover:bg-green-50"
                      >
                        {downloadingIds.has(audit.id) ? (
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        ) : (
                          <Download className="w-4 h-4 mr-2" />
                        )}
                        Download PDF
                      </Button>
                    ) : (
                      <Button size="sm" variant="outline" disabled className="text-gray-500 bg-transparent">
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        Generating PDF...
                      </Button>
                    )}
                  </>
                )}
                {audit.status === "FAILED" && audit.error_message && (
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          size="sm"
                          variant="outline"
                          className="border-red-600 text-red-700 hover:bg-red-50 bg-transparent"
                        >
                          <AlertCircle className="w-4 h-4 mr-2" />
                          View Error
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent side="left" className="max-w-[300px]">
                        <p className="text-sm">{audit.error_message}</p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
