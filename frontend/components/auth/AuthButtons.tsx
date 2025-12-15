"use client";

import { useUser } from "@auth0/nextjs-auth0/client";
import { Button } from "@/components/ui/button";
import { LogOut, User, Loader2 } from "lucide-react";

export function AuthButtons() {
    const { user, isLoading } = useUser();

    if (isLoading) {
        return (
            <div className="flex items-center gap-2 text-white/60">
                <Loader2 className="w-4 h-4 animate-spin" />
            </div>
        );
    }

    if (user) {
        return (
            <div className="flex items-center gap-3">
                <div className="flex items-center gap-2 px-3 py-1.5 bg-white/5 rounded-xl border border-white/10">
                    <img
                        src={user.picture || undefined}
                        alt={user.name || "User"}
                        className="w-7 h-7 rounded-full border border-white/20"
                        onError={(e) => {
                            const target = e.target as HTMLImageElement;
                            target.style.display = 'none';
                        }}
                    />
                    <span className="text-sm font-medium text-white/80 max-w-[120px] truncate">
                        {user.name || user.email}
                    </span>
                </div>
                <a href="/auth/logout">
                    <Button
                        variant="ghost"
                        size="sm"
                        className="text-red-400 hover:text-red-300 hover:bg-red-500/10 rounded-xl gap-2"
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
                    className="text-white/70 hover:text-white hover:bg-white/10 rounded-xl"
                >
                    Sign in
                </Button>
            </a>
            <a href="/auth/login">
                <Button
                    size="sm"
                    className="bg-white text-black hover:bg-white/90 rounded-xl font-medium px-6 shadow-lg shadow-white/10"
                >
                    Get Started
                </Button>
            </a>
        </div>
    );
}
