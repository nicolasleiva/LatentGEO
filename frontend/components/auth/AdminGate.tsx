"use client"

import type { ReactNode } from "react"
import { useUser } from "@auth0/nextjs-auth0/client"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Loader2, Lock } from "lucide-react"

export function AdminGate({ children, title }: { children: ReactNode; title?: string }) {
  const { user, isLoading } = useUser()

  if (isLoading) {
    return (
      <div className="max-w-4xl mx-auto px-6 py-12">
        <Card className="glass-card p-10 text-center">
          <Loader2 className="h-6 w-6 animate-spin mx-auto mb-3" />
          <div className="text-muted-foreground">Cargando sesión...</div>
        </Card>
      </div>
    )
  }

  if (!user) {
    return (
      <div className="max-w-4xl mx-auto px-6 py-12">
        <Card className="glass-card p-10 text-center">
          <Lock className="h-10 w-10 text-muted-foreground/60 mx-auto mb-4" />
          <div className="text-xl font-semibold">{title || "Acceso restringido"}</div>
          <div className="text-muted-foreground mt-2">
            Iniciá sesión para acceder a esta sección.
          </div>
          <div className="mt-6">
            <a href="/auth/login">
              <Button>Sign in</Button>
            </a>
          </div>
        </Card>
      </div>
    )
  }

  return <>{children}</>
}
