"use client"

import type React from "react"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { createAudit } from "@/lib/api"
import { Loader2 } from "lucide-react"
import { useToast } from "@/hooks/use-toast"

interface NewAuditModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess: () => void
}

export function NewAuditModal({ open, onOpenChange, onSuccess }: NewAuditModalProps) {
  const [url, setUrl] = useState("")
  const [maxCrawl, setMaxCrawl] = useState("100")
  const [maxAudit, setMaxAudit] = useState("50")
  const [isSubmitting, setIsSubmitting] = useState(false)
  const { toast } = useToast()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!url.trim()) {
      toast({
        title: "Validation Error",
        description: "Please enter a valid URL",
        variant: "destructive",
      })
      return
    }

    setIsSubmitting(true)

    try {
      await createAudit({
        url: url.trim(),
        max_crawl: Number.parseInt(maxCrawl) || 100,
        max_audit: Number.parseInt(maxAudit) || 50,
      })

      toast({
        title: "Audit Created",
        description: "Your audit has been queued and will start processing shortly.",
      })

      setUrl("")
      setMaxCrawl("100")
      setMaxAudit("50")
      onOpenChange(false)
      onSuccess()
    } catch (error) {
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to create audit",
        variant: "destructive",
      })
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Launch New Audit</DialogTitle>
            <DialogDescription>
              Enter the URL you want to audit. The system will crawl and analyze the site for SEO issues.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="url">Website URL *</Label>
              <Input
                id="url"
                type="url"
                placeholder="https://example.com"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                required
                disabled={isSubmitting}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="maxCrawl">Max Crawl Pages</Label>
                <Input
                  id="maxCrawl"
                  type="number"
                  placeholder="100"
                  value={maxCrawl}
                  onChange={(e) => setMaxCrawl(e.target.value)}
                  disabled={isSubmitting}
                />
              </div>

              <div className="grid gap-2">
                <Label htmlFor="maxAudit">Max Audit Pages</Label>
                <Input
                  id="maxAudit"
                  type="number"
                  placeholder="50"
                  value={maxAudit}
                  onChange={(e) => setMaxAudit(e.target.value)}
                  disabled={isSubmitting}
                />
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={isSubmitting}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              Launch Audit
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
