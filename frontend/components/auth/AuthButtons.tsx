"use client";

import { useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Loader2, LogOut, User } from "lucide-react";
import { logoutAllSessions, useAppAuthState, useCombinedProfile } from "@/lib/app-auth";

export function AuthButtons() {
  const auth = useAppAuthState();
  const profile = useCombinedProfile(auth);

  const handleLogout = useCallback(() => {
    logoutAllSessions();
  }, []);

  if (auth.loading) {
    return (
      <div className="flex items-center gap-2 text-foreground/60">
        <Loader2 className="w-4 h-4 animate-spin" />
      </div>
    );
  }

  if (auth.ready) {
    return (
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 px-3 py-1.5 bg-background/70 rounded-xl border border-border/70">
          <div className="relative w-7 h-7 flex items-center justify-center bg-brand/10 rounded-full">
            <User className="w-4 h-4 text-brand" />
          </div>
          <span className="text-sm font-medium text-foreground/80 max-w-[120px] truncate">
            {profile.email}
          </span>
        </div>
        <Button
          onClick={handleLogout}
          variant="ghost"
          size="sm"
          className="text-red-500 hover:text-red-600 hover:bg-red-500/10 rounded-xl gap-2"
        >
          <LogOut className="w-4 h-4" />
          Logout
        </Button>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-4">
      <Button
        asChild
        variant="ghost"
        size="sm"
        className="text-foreground/70 hover:text-foreground hover:bg-foreground/5 rounded-xl"
      >
        <a href="/auth/login">Iniciar Sesión</a>
      </Button>
      <Button
        asChild
        size="sm"
        className="bg-brand text-brand-foreground hover:bg-brand/90 rounded-xl font-medium px-6 shadow-[0_12px_30px_rgba(16,185,129,0.25)]"
      >
        <a href="/auth/login?screen_hint=signup">Crear Cuenta</a>
      </Button>
    </div>
  );
}
