"use client";

import { useEffect, useState } from "react";
import { Header } from "@/components/header";
import { AdminGate } from "@/components/auth/AdminGate";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { API_URL } from "@/lib/api";
import { Activity, RefreshCw } from "lucide-react";

type HealthResult = { name: string; status: number | null; data: any };

export default function HealthOpsPage() {
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<HealthResult[]>([]);

  const load = async () => {
    setLoading(true);
    try {
      const endpoints: Array<{ name: string; url: string }> = [
        { name: "GET /health", url: `${API_URL}/health` },
        { name: "GET /health/ready", url: `${API_URL}/health/ready` },
        { name: "GET /health/live", url: `${API_URL}/health/live` },
        {
          name: "GET /api/v1/webhooks/health",
          url: `${API_URL}/api/v1/webhooks/health`,
        },
      ];

      const data = await Promise.all(
        endpoints.map(async (e) => {
          try {
            const res = await fetch(e.url);
            const json = await res.json().catch(() => ({}));
            return { name: e.name, status: res.status, data: json };
          } catch (err) {
            return { name: e.name, status: null, data: { error: String(err) } };
          }
        }),
      );

      setResults(data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Header />
      <AdminGate title="Health / Ops">
        <main className="max-w-6xl mx-auto px-6 py-12 space-y-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h1 className="text-3xl font-bold flex items-center gap-3">
                <Activity className="h-7 w-7" />
                Health / Ops
              </h1>
              <p className="text-muted-foreground mt-1">
                Estado del sistema (backend + webhooks)
              </p>
            </div>
            <Button variant="outline" onClick={load} disabled={loading}>
              <RefreshCw
                className={
                  loading ? "h-4 w-4 mr-2 animate-spin" : "h-4 w-4 mr-2"
                }
              />
              Reload
            </Button>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {results.map((r) => (
              <Card key={r.name} className="glass-card p-6">
                <div className="flex items-center justify-between gap-4 mb-3">
                  <div className="font-semibold">{r.name}</div>
                  <div className="text-sm text-muted-foreground">
                    {r.status === null ? "ERR" : `HTTP ${r.status}`}
                  </div>
                </div>
                <pre className="text-xs bg-muted/40 border border-border rounded-xl p-4 overflow-auto max-h-[55vh]">
                  {JSON.stringify(r.data, null, 2)}
                </pre>
              </Card>
            ))}
          </div>
        </main>
      </AdminGate>
    </div>
  );
}

