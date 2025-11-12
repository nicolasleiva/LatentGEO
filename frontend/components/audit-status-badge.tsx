import { Badge } from "@/components/ui/badge"
import type { AuditStatus } from "@/lib/types"
import { Clock, Loader2, CheckCircle2, XCircle } from "lucide-react"

interface AuditStatusBadgeProps {
  status: AuditStatus
}

const statusConfig = {
  PENDING: {
    label: "Pending",
    className: "bg-muted text-muted-foreground border-muted-foreground/20",
    icon: Clock,
  },
  RUNNING: {
    label: "Running",
    className: "bg-warning/10 text-warning border-warning/30",
    icon: Loader2,
  },
  COMPLETED: {
    label: "Completed",
    className: "bg-success/10 text-success border-success/30",
    icon: CheckCircle2,
  },
  FAILED: {
    label: "Failed",
    className: "bg-destructive/10 text-destructive border-destructive/30",
    icon: XCircle,
  },
}

export function AuditStatusBadge({ status }: AuditStatusBadgeProps) {
  const config = statusConfig[status]

  if (!config) {
    return null // Or return a default/unknown status badge
  }

  const Icon = config.icon

  return (
    <Badge variant="outline" className={config.className}>
      <Icon className={`w-3 h-3 mr-1.5 ${status === "RUNNING" ? "animate-spin" : ""}`} />
      {config.label}
    </Badge>
  )
}
