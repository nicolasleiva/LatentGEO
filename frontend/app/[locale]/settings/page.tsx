"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useTheme } from "next-themes";
import Image from "next/image";
import { Header } from "@/components/header";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useCombinedProfile, useRequireAppAuth } from "@/lib/app-auth";
import {
  User,
  Bell,
  Key,
  Palette,
  Shield,
  Save,
  Moon,
  Sun,
  Monitor,
  Check,
} from "lucide-react";

type NotificationPreferences = {
  email: boolean;
  auditComplete: boolean;
  weeklyReport: boolean;
};

const DEFAULT_NOTIFICATIONS: NotificationPreferences = {
  email: true,
  auditComplete: true,
  weeklyReport: false,
};

export default function SettingsPage() {
  const auth = useRequireAppAuth();
  const profile = useCombinedProfile(auth);
  const user = auth.ready ? profile : null;
  const isLoading = auth.loading || !auth.ready;
  const { theme, setTheme } = useTheme();
  const [displayName, setDisplayName] = useState("");
  const [notifications, setNotifications] =
    useState<NotificationPreferences>(DEFAULT_NOTIFICATIONS);
  const [saved, setSaved] = useState(false);

  const storagePrefix = useMemo(() => {
    const userKey = user?.id || user?.email || "anonymous";
    return `latentgeo:settings:${userKey}`;
  }, [user?.email, user?.id]);

  useEffect(() => {
    if (!user) return;

    const storedName = localStorage.getItem(`${storagePrefix}:displayName`);
    const storedNotifications = localStorage.getItem(
      `${storagePrefix}:notifications`,
    );

    setDisplayName(storedName || user.name || "");

    if (storedNotifications) {
      try {
        const parsed = JSON.parse(storedNotifications) as NotificationPreferences;
        setNotifications({
          email: Boolean(parsed.email),
          auditComplete: Boolean(parsed.auditComplete),
          weeklyReport: Boolean(parsed.weeklyReport),
        });
      } catch {
        setNotifications(DEFAULT_NOTIFICATIONS);
      }
    } else {
      setNotifications(DEFAULT_NOTIFICATIONS);
    }
  }, [storagePrefix, user]);

  const handleSave = () => {
    localStorage.setItem(`${storagePrefix}:displayName`, displayName.trim());
    localStorage.setItem(
      `${storagePrefix}:notifications`,
      JSON.stringify(notifications),
    );

    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const handleCancel = () => {
    const storedName = localStorage.getItem(`${storagePrefix}:displayName`);
    const storedNotifications = localStorage.getItem(
      `${storagePrefix}:notifications`,
    );

    setDisplayName(storedName || user?.name || "");
    if (storedNotifications) {
      try {
        setNotifications(
          JSON.parse(storedNotifications) as NotificationPreferences,
        );
      } catch {
        setNotifications(DEFAULT_NOTIFICATIONS);
      }
    } else {
      setNotifications(DEFAULT_NOTIFICATIONS);
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background">
        <Header />
        <div className="flex items-center justify-center h-[60vh]">
          <div className="w-8 h-8 border-2 border-muted-foreground border-t-foreground rounded-full animate-spin" />
        </div>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="min-h-screen bg-background">
        <Header />
        <div className="max-w-4xl mx-auto px-6 py-16 text-center">
          <Shield className="w-16 h-16 text-muted-foreground/50 mx-auto mb-6" />
          <h1 className="text-3xl font-bold text-foreground mb-4">
            Sign in Required
          </h1>
          <p className="text-muted-foreground mb-8">
            Please sign in to access your settings.
          </p>
          <Link
            href="/auth/login"
            className="inline-flex items-center gap-2 px-6 py-3 bg-primary text-primary-foreground rounded-xl font-medium hover:bg-primary/90 transition-colors"
          >
            Sign In
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Header />

      <main className="max-w-4xl mx-auto px-6 py-12">
        <div className="mb-8">
          <h1 className="text-3xl font-bold mb-2">Workspace Settings</h1>
          <p className="text-muted-foreground">
            Configure identity, appearance, and notification behavior.
          </p>
        </div>

        <div className="space-y-6">
          {/* Profile Section */}
          <section className="p-6 glass-card border border-border rounded-2xl">
            <div className="flex items-center gap-3 mb-6">
              <User className="w-5 h-5 text-brand" />
              <h2 className="text-lg font-semibold">Profile & Workspace Identity</h2>
            </div>

            <div className="flex items-center gap-6 mb-6">
              {user.picture ? (
                <div className="relative w-20 h-20">
                  <Image
                    src={user.picture}
                    alt={user.name || "User"}
                    fill
                    sizes="80px"
                    className="rounded-full border-2 border-border object-cover"
                    unoptimized
                  />
                </div>
              ) : (
                <div className="w-20 h-20 rounded-full bg-gradient-to-br from-emerald-500 to-emerald-700 flex items-center justify-center text-2xl font-bold text-white">
                  {user.name?.charAt(0) || user.email?.charAt(0) || "U"}
                </div>
              )}
              <div>
                <h3 className="text-xl font-medium">{user.name || "User"}</h3>
                <p className="text-muted-foreground">{user.email}</p>
                <Badge className="mt-2 bg-emerald-500/10 text-emerald-600 border-emerald-500/20">
                  Growth-ready workspace
                </Badge>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label
                  htmlFor="display-name"
                  className="block text-sm text-muted-foreground mb-2"
                >
                  Display Name
                </label>
                <input
                  id="display-name"
                  type="text"
                  value={displayName}
                  onChange={(event) => setDisplayName(event.target.value)}
                  className="w-full px-4 py-3 glass-panel border border-border rounded-xl text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-border/80"
                  placeholder="Your name"
                />
              </div>
              <div>
                <label
                  htmlFor="account-email"
                  className="block text-sm text-muted-foreground mb-2"
                >
                  Email
                </label>
                <input
                  id="account-email"
                  type="email"
                  value={user.email || ""}
                  disabled
                  className="w-full px-4 py-3 glass-panel border border-border rounded-xl text-muted-foreground cursor-not-allowed"
                />
              </div>
            </div>
          </section>

          {/* Appearance Section */}
          <section className="p-6 glass-card border border-border rounded-2xl">
            <div className="flex items-center gap-3 mb-6">
              <Palette className="w-5 h-5 text-brand" />
              <h2 className="text-lg font-semibold">Appearance Mode</h2>
            </div>

            <div className="flex gap-4">
              <button
                onClick={() => setTheme("dark")}
                className={`flex-1 p-4 rounded-xl border transition-all ${
                  theme === "dark"
                    ? "bg-muted border-border/80"
                    : "glass-panel border-border hover:border-border/80"
                }`}
              >
                <Moon className="w-6 h-6 mx-auto mb-2" />
                <p className="text-sm">Dark</p>
              </button>
              <button
                onClick={() => setTheme("light")}
                className={`flex-1 p-4 rounded-xl border transition-all ${
                  theme === "light"
                    ? "bg-muted border-border/80"
                    : "glass-panel border-border hover:border-border/80"
                }`}
              >
                <Sun className="w-6 h-6 mx-auto mb-2" />
                <p className="text-sm">Light</p>
              </button>
              <button
                onClick={() => setTheme("system")}
                className={`flex-1 p-4 rounded-xl border transition-all ${
                  theme === "system"
                    ? "bg-muted border-border/80"
                    : "glass-panel border-border hover:border-border/80"
                }`}
              >
                <Monitor className="w-6 h-6 mx-auto mb-2" />
                <p className="text-sm">System</p>
              </button>
            </div>
          </section>

          {/* Notifications Section */}
          <section className="p-6 glass-card border border-border rounded-2xl">
            <div className="flex items-center gap-3 mb-6">
              <Bell className="w-5 h-5 text-amber-500" />
              <h2 className="text-lg font-semibold">Notifications</h2>
            </div>

            <div className="space-y-4">
              <div className="flex items-center justify-between p-4 glass-panel rounded-xl hover:bg-muted/50 transition-colors">
                <div>
                  <p className="font-medium">Email Notifications</p>
                  <p className="text-sm text-muted-foreground">
                    Receive product and workflow updates by email
                  </p>
                </div>
                <input
                  type="checkbox"
                  aria-label="Email Notifications"
                  checked={notifications.email}
                  onChange={(e) =>
                    setNotifications({
                      ...notifications,
                      email: e.target.checked,
                    })
                  }
                  className="w-5 h-5 accent-brand"
                />
              </div>

              <div className="flex items-center justify-between p-4 glass-panel rounded-xl hover:bg-muted/50 transition-colors">
                <div>
                  <p className="font-medium">Audit Complete</p>
                  <p className="text-sm text-muted-foreground">
                    Notify when a queued audit reaches completion
                  </p>
                </div>
                <input
                  type="checkbox"
                  aria-label="Audit Complete"
                  checked={notifications.auditComplete}
                  onChange={(e) =>
                    setNotifications({
                      ...notifications,
                      auditComplete: e.target.checked,
                    })
                  }
                  className="w-5 h-5 accent-brand"
                />
              </div>

              <div className="flex items-center justify-between p-4 glass-panel rounded-xl hover:bg-muted/50 transition-colors">
                <div>
                  <p className="font-medium">Weekly Report</p>
                  <p className="text-sm text-muted-foreground">
                    Receive a weekly summary of your audit activity
                  </p>
                </div>
                <input
                  type="checkbox"
                  aria-label="Weekly Report"
                  checked={notifications.weeklyReport}
                  onChange={(e) =>
                    setNotifications({
                      ...notifications,
                      weeklyReport: e.target.checked,
                    })
                  }
                  className="w-5 h-5 accent-brand"
                />
              </div>
            </div>
          </section>

          <section className="p-6 glass-card border border-border rounded-2xl">
            <div className="flex items-center gap-3 mb-6">
              <Shield className="w-5 h-5 text-brand" />
              <h2 className="text-lg font-semibold">Security & Access</h2>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="p-4 glass-panel rounded-xl border border-border">
                <p className="text-sm text-muted-foreground mb-1">
                  Authentication Provider
                </p>
                <p className="font-medium">Supabase + Auth0 (Google)</p>
              </div>
              <div className="p-4 glass-panel rounded-xl border border-border">
                <p className="text-sm text-muted-foreground mb-1">Session</p>
                <p className="font-medium">Managed securely by provider</p>
              </div>
            </div>
          </section>

          {/* API Keys Section */}
          <section className="p-6 glass-card border border-border rounded-2xl">
            <div className="flex items-center gap-3 mb-6">
              <Key className="w-5 h-5 text-green-500" />
              <h2 className="text-lg font-semibold">Developer Access</h2>
              <Badge className="bg-brand/10 text-brand border-brand/20">
                Private Beta
              </Badge>
            </div>

            <p className="text-muted-foreground mb-4">
              Request access to typed API tokens for CI integrations and internal tooling.
            </p>

            <Button disabled>Request API Access</Button>
          </section>

          {/* Save Button */}
          <div className="flex justify-end gap-4">
            <Button variant="outline" onClick={handleCancel}>
              Revert
            </Button>
            <Button
              onClick={handleSave}
              className={`${saved ? "bg-emerald-500" : "bg-brand"} text-brand-foreground hover:opacity-90 transition-all`}
            >
              {saved ? (
                <>
                  <Check className="w-4 h-4 mr-2" />
                  Preferences Saved
                </>
              ) : (
                <>
                  <Save className="w-4 h-4 mr-2" />
                  Save Preferences
                </>
              )}
            </Button>
          </div>
        </div>
      </main>
    </div>
  );
}
