"use client";

import { useUser } from "@auth0/nextjs-auth0/client";
import Image from "next/image";
import { Button } from "@/components/ui/button";
import { LogOut, Loader2 } from "lucide-react";

export function AuthButtons() {
    const { user, isLoading } = useUser();

    if (isLoading) {
        return (
            <div className="flex items-center gap-2 text-foreground/60">
                <Loader2 className="w-4 h-4 animate-spin" />
            </div>
        );
    }

    if (user) {
        return (
            <div className="flex items-center gap-3">
                <div className="flex items-center gap-2 px-3 py-1.5 bg-background/70 rounded-xl border border-border/70">
                    <div className="relative w-7 h-7">
                        <Image
                            src={user.picture || "/default-avatar.png"}
                            alt={user.name || "User"}
                            fill
                            className="rounded-full border border-border/60 object-cover"
                            unoptimized
                        />
                    </div>
                    <span className="text-sm font-medium text-foreground/80 max-w-[120px] truncate">
                        {user.name || user.email}
                    </span>
                </div>
                <a href="/auth/logout">
                    <Button
                        variant="ghost"
                        size="sm"
                        className="text-red-500 hover:text-red-600 hover:bg-red-500/10 rounded-xl gap-2"
                    >
                        <LogOut className="w-4 h-4" />
                        Logout
                    </Button>
                </a>
            </div>
        );
    }

    return (
        <div className="flex items-center gap-4">
            <a href="/auth/login">
                <Button
                    variant="ghost"
                    size="sm"
                    className="text-foreground/70 hover:text-foreground hover:bg-foreground/5 rounded-xl"
                >
                    Sign in
                </Button>
            </a>
            <a href="/auth/login">
                <Button
                    size="sm"
                    className="bg-brand text-brand-foreground hover:bg-brand/90 rounded-xl font-medium px-6 shadow-[0_12px_30px_rgba(16,185,129,0.25)]"
                >
                    Start audit
                </Button>
            </a>
        </div>
    );
}
