"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { RefreshCw, Play, ExternalLink } from "lucide-react";
import { API_URL } from "@/lib/api";
import { fetchWithBackendAuth } from "@/lib/backend-auth";

interface HubSpotPage {
  id: string;
  hubspot_id: string;
  url: string;
  title: string;
  last_synced_at: string;
}

interface Connection {
  id: string;
  portal_id: string;
}

export default function HubSpotPages() {
  const router = useRouter();
  const [connection, setConnection] = useState<Connection | null>(null);
  const [pages, setPages] = useState<HubSpotPage[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [auditing, setAuditing] = useState(false);

  useEffect(() => {
    fetchConnection();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchConnection = async () => {
    try {
      const res = await fetchWithBackendAuth(
        `${API_URL}/api/hubspot/connections`,
      );
      const data = await res.json();
      if (data && data.length > 0) {
        setConnection(data[0]);
        fetchPages(data[0].id);
      } else {
        setLoading(false);
      }
    } catch (error) {
      console.error(error);
      setLoading(false);
    }
  };

  const fetchPages = async (connId: string) => {
    try {
      const res = await fetchWithBackendAuth(
        `${API_URL}/api/hubspot/pages/${connId}`,
      );
      const data = await res.json();
      setPages(data);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleSync = async () => {
    if (!connection) return;
    setSyncing(true);
    try {
      await fetchWithBackendAuth(
        `${API_URL}/api/hubspot/sync/${connection.id}`,
        { method: "POST" },
      );
      await fetchPages(connection.id);
    } catch (error) {
      console.error(error);
    } finally {
      setSyncing(false);
    }
  };

  const togglePage = (id: string) => {
    const newSelected = new Set(selected);
    if (newSelected.has(id)) {
      newSelected.delete(id);
    } else {
      newSelected.add(id);
    }
    setSelected(newSelected);
  };

  const handleAudit = async () => {
    if (selected.size === 0) return;
    setAuditing(true);
    try {
      // Create audit
      const selectedPages = pages.filter((p) => selected.has(p.id));

      // We need an endpoint to start audit for multiple URLs.
      // Existing /api/audits takes a single URL usually.
      // Let's assume we create one audit per URL or one audit with multiple pages.
      // The current system seems to support one URL per audit (Audit model has 'url').
      // So we will loop and create multiple audits or create a "project".
      // For simplicity, let's just audit the first one or loop.
      // Wait, the user wants to audit "pages".
      // Let's create a new endpoint /api/audits/batch or just loop here.

      // Process all selected pages in parallel
      await Promise.all(
        selectedPages.map((page) =>
          fetchWithBackendAuth(`${API_URL}/api/v1/audits/`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ url: page.url, source: "hubspot" }),
          }),
        ),
      );

      // Redirect to the audits list or dashboard after initiating all audits
      router.push("/audits");
    } catch (error) {
      console.error(error);
    } finally {
      setAuditing(false);
    }
  };

  if (loading) {
    return <div className="p-8 text-center">Loading...</div>;
  }

  if (!connection) {
    return (
      <div className="container mx-auto py-20 text-center">
        <h1 className="text-2xl font-bold mb-4">No HubSpot Connection Found</h1>
        <Button onClick={() => router.push("/integrations/hubspot/connect")}>
          Connect HubSpot
        </Button>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-8">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-bold">HubSpot Pages</h1>
          <p className="text-muted-foreground">
            Portal ID: {connection.portal_id} • {pages.length} pages found
          </p>
        </div>
        <div className="flex gap-3">
          <Button variant="outline" onClick={handleSync} disabled={syncing}>
            <RefreshCw
              className={`w-4 h-4 mr-2 ${syncing ? "animate-spin" : ""}`}
            />
            Sync Pages
          </Button>
          <Button
            onClick={handleAudit}
            disabled={selected.size === 0 || auditing}
          >
            <Play className="w-4 h-4 mr-2" />
            Audit Selected ({selected.size})
          </Button>
        </div>
      </div>

      <div className="grid gap-4">
        {pages.map((page) => (
          <Card
            key={page.id}
            className={selected.has(page.id) ? "border-primary" : ""}
          >
            <CardContent className="p-4 flex items-center gap-4">
              <Checkbox
                checked={selected.has(page.id)}
                onCheckedChange={() => togglePage(page.id)}
              />
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <h3 className="font-medium">{page.title || page.url}</h3>
                  <a
                    href={page.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-muted-foreground hover:text-primary"
                  >
                    <ExternalLink className="w-3 h-3" />
                  </a>
                </div>
                <p className="text-sm text-muted-foreground truncate">
                  {page.url}
                </p>
              </div>
              <div className="text-sm text-muted-foreground">
                Last synced:{" "}
                {new Date(page.last_synced_at).toLocaleDateString()}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
