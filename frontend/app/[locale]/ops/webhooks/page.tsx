"use client";

import { useState } from "react";
import { Header } from "@/components/header";
import { AdminGate } from "@/components/auth/AdminGate";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { API_URL } from "@/lib/api";
import { Loader2, RefreshCw, Webhook } from "lucide-react";

export default function WebhooksOpsPage() {
  const [configUrl, setConfigUrl] = useState("");
  const [configSecret, setConfigSecret] = useState("");
  const [configEvents, setConfigEvents] = useState(
    "audit.completed\npdf.ready",
  );
  const [testEvent, setTestEvent] = useState("audit.completed");
  const [loading, setLoading] = useState(false);
  const [output, setOutput] = useState<any>(null);
  const [error, setError] = useState<string>("");

  const run = async (label: string, fn: () => Promise<any>) => {
    setLoading(true);
    setError("");
    try {
      const data = await fn();
      setOutput({ action: label, data });
    } catch (e: any) {
      console.error(e);
      setError(e?.message || "Error executing action.");
      setOutput({ action: label, error: e?.message || String(e) });
    } finally {
      setLoading(false);
    }
  };

  const eventsList = () =>
    configEvents
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Header />
      <AdminGate title="Webhooks">
        <main className="max-w-6xl mx-auto px-6 py-12 space-y-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h1 className="text-3xl font-bold flex items-center gap-3">
                <Webhook className="h-7 w-7" />
                Webhooks
              </h1>
              <p className="text-muted-foreground mt-1">
                Configurar y testear webhooks (endpoints entrantes no se invocan
                desde UI)
              </p>
            </div>
            <Button
              variant="outline"
              disabled={loading}
              onClick={() =>
                run("GET /webhooks/events", async () => {
                  const res = await fetch(`${API_URL}/api/webhooks/events`);
                  const data = await res.json().catch(() => ({}));
                  if (!res.ok)
                    throw new Error(data?.detail || `HTTP ${res.status}`);
                  return data;
                })
              }
            >
              {loading ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <RefreshCw className="h-4 w-4 mr-2" />
              )}
              List Events
            </Button>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card className="glass-card p-6 space-y-4">
              <div className="text-lg font-semibold">Config</div>
              <div className="space-y-2">
                <Label>URL</Label>
                <Input
                  value={configUrl}
                  onChange={(e) => setConfigUrl(e.target.value)}
                  placeholder="https://example.com/webhook"
                />
              </div>
              <div className="space-y-2">
                <Label>Secret (opcional)</Label>
                <Input
                  value={configSecret}
                  onChange={(e) => setConfigSecret(e.target.value)}
                  placeholder="min 16 chars"
                />
              </div>
              <div className="space-y-2">
                <Label>Events (one per line)</Label>
                <Textarea
                  value={configEvents}
                  onChange={(e) => setConfigEvents(e.target.value)}
                  className="min-h-[120px] font-mono text-xs"
                />
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  disabled={loading || !configUrl}
                  onClick={() =>
                    run("POST /webhooks/config", async () => {
                      const res = await fetch(
                        `${API_URL}/api/webhooks/config`,
                        {
                          method: "POST",
                          headers: { "Content-Type": "application/json" },
                          body: JSON.stringify({
                            url: configUrl,
                            secret: configSecret || null,
                            events: eventsList(),
                            active: true,
                            description: "Configured from UI",
                          }),
                        },
                      );
                      const data = await res.json().catch(() => ({}));
                      if (!res.ok)
                        throw new Error(data?.detail || `HTTP ${res.status}`);
                      return data;
                    })
                  }
                >
                  Save Config
                </Button>
              </div>
            </Card>

            <Card className="glass-card p-6 space-y-4">
              <div className="text-lg font-semibold">Test</div>
              <div className="space-y-2">
                <Label>Event type</Label>
                <Input
                  value={testEvent}
                  onChange={(e) => setTestEvent(e.target.value)}
                  placeholder="audit.completed"
                />
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="outline"
                  disabled={loading || !configUrl}
                  onClick={() =>
                    run("POST /webhooks/test", async () => {
                      const res = await fetch(`${API_URL}/api/webhooks/test`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                          url: configUrl,
                          secret: configSecret || null,
                          event_type: testEvent,
                        }),
                      });
                      const data = await res.json().catch(() => ({}));
                      if (!res.ok)
                        throw new Error(data?.detail || `HTTP ${res.status}`);
                      return data;
                    })
                  }
                >
                  Send Test Event
                </Button>
                <Button
                  variant="outline"
                  disabled={loading}
                  onClick={() =>
                    run("GET /webhooks/health", async () => {
                      const res = await fetch(`${API_URL}/api/webhooks/health`);
                      const data = await res.json().catch(() => ({}));
                      if (!res.ok)
                        throw new Error(data?.detail || `HTTP ${res.status}`);
                      return data;
                    })
                  }
                >
                  Webhooks Health
                </Button>
              </div>
            </Card>
          </div>

          <Card className="glass-card p-6">
            <div className="flex items-center justify-between gap-4 mb-3">
              <div className="text-lg font-semibold">Output</div>
              {error && <div className="text-sm text-red-400">{error}</div>}
            </div>
            <pre className="text-xs bg-muted/40 border border-border rounded-xl p-4 overflow-auto max-h-[60vh]">
              {JSON.stringify(output, null, 2)}
            </pre>
          </Card>
        </main>
      </AdminGate>
    </div>
  );
}
