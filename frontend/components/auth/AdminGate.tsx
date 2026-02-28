"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Loader2, Lock } from "lucide-react";
import { useRequireAppAuth } from "@/lib/app-auth";

export function AdminGate({
  children,
  title,
}: {
  children: ReactNode;
  title?: string;
}) {
  const auth = useRequireAppAuth();

  if (auth.loading) {
    return (
      <div className="max-w-4xl mx-auto px-6 py-12">
        <Card className="glass-card p-10 text-center">
          <Loader2 className="h-6 w-6 animate-spin mx-auto mb-3" />
          <div className="text-muted-foreground">Loading session...</div>
        </Card>
      </div>
    );
  }

  if (!auth.ready) {
    return (
      <div className="max-w-4xl mx-auto px-6 py-12">
        <Card className="glass-card p-10 text-center">
          <Lock className="h-10 w-10 text-muted-foreground/60 mx-auto mb-4" />
          <div className="text-xl font-semibold">
            {title || "Restricted access"}
          </div>
          <div className="text-muted-foreground mt-2">
            Sign in to access this section.
          </div>
          <div className="mt-6">
            <Link href="/auth/login">
              <Button>Sign in</Button>
            </Link>
          </div>
        </Card>
      </div>
    );
  }

  return <>{children}</>;
}
