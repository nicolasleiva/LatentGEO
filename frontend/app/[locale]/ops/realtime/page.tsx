"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Header } from "@/components/header";
import { AdminGate } from "@/components/auth/AdminGate";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { API_URL } from "@/lib/api";
import { Radio, StopCircle } from "lucide-react";

export default function RealtimeOpsPage() {
  const [auditId, setAuditId] = useState("");
  const [connected, setConnected] = useState(false);
  const [messages, setMessages] = useState<string[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  const wsUrl = useMemo(() => {
    const base = API_URL.replace(/^http/, "ws");
    const id = auditId.trim();
    return `${base}/ws/progress/${encodeURIComponent(id)}`;
  }, [auditId]);

  const connect = () => {
    const id = auditId.trim();
    if (!id) return;
    if (wsRef.current) wsRef.current.close();

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;
    setMessages((prev) => [`Connecting to ${wsUrl}`, ...prev].slice(0, 200));

    ws.onopen = () => {
      setConnected(true);
      setMessages((prev) => ["WS connected", ...prev].slice(0, 200));
    };
    ws.onmessage = (event) => {
      setMessages((prev) => [String(event.data), ...prev].slice(0, 200));
    };
    ws.onerror = () => {
      setMessages((prev) => ["WS error", ...prev].slice(0, 200));
    };
    ws.onclose = () => {
      setConnected(false);
      setMessages((prev) => ["WS closed", ...prev].slice(0, 200));
    };
  };

  const disconnect = () => {
    wsRef.current?.close();
    wsRef.current = null;
  };

  useEffect(() => {
    return () => disconnect();
  }, []);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Header />
      <AdminGate title="Realtime">
        <main className="max-w-5xl mx-auto px-6 py-12 space-y-6">
          <div>
            <h1 className="text-3xl font-bold flex items-center gap-3">
              <Radio className="h-7 w-7" />
              Realtime (WebSocket)
            </h1>
            <p className="text-muted-foreground mt-1">
              Direct connection to the progress WS endpoint
            </p>
          </div>

          <Card className="glass-card p-6">
            <div className="flex flex-col md:flex-row gap-3 md:items-end">
              <div className="flex-1 space-y-2">
                <Label>audit_id</Label>
                <Input
                  value={auditId}
                  onChange={(e) => setAuditId(e.target.value)}
                  placeholder="Ej: 123"
                />
              </div>
              <div className="flex gap-2">
                <Button
                  onClick={connect}
                  disabled={connected || !auditId.trim()}
                >
                  Connect
                </Button>
                <Button
                  variant="outline"
                  onClick={disconnect}
                  disabled={!connected}
                >
                  <StopCircle className="h-4 w-4 mr-2" />
                  Disconnect
                </Button>
              </div>
            </div>

            <div className="text-sm text-muted-foreground mt-4">
              Status: {connected ? "connected" : "disconnected"} — URL: {wsUrl}
            </div>
          </Card>

          <Card className="glass-card p-6">
            <div className="text-lg font-semibold mb-3">Messages</div>
            <pre className="text-xs bg-muted/40 border border-border rounded-xl p-4 overflow-auto max-h-[70vh]">
              {messages.join("\n")}
            </pre>
          </Card>
        </main>
      </AdminGate>
    </div>
  );
}
