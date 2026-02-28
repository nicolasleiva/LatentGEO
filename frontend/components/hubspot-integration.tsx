"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  CheckCircle2,
  XCircle,
  Clock,
  LogOut,
  Sparkles,
} from "lucide-react";
import { fetchWithBackendAuth } from "@/lib/backend-auth";

interface HubSpotIntegrationProps {
  auditId: string;
  auditUrl: string;
}

interface HubSpotConnection {
  id: string;
  portal_id: string;
  created_at: string;
  is_active: boolean;
}

interface HubSpotPage {
  id: string;
  hubspot_id: string;
  connection_id: string;
  url: string;
  title: string;
  html_title: string;
  meta_description: string;
}

interface Recommendation {
  id: string;
  hubspot_page_id: string;
  page_url: string;
  page_title: string;
  field: string;
  current_value: string | null;
  recommended_value: string;
  priority: "high" | "medium" | "low";
  auto_fixable: boolean;
  issue_type: string;
}

interface ApplyResult {
  success: boolean;
  page_id: string;
  field: string;
  error?: string;
  page_path?: string;
  issue_code?: string;
}

function HubSpotConnectCard({ onConnect }: { onConnect: () => void }) {
  return (
    <Card className="glass-card p-6">
      <div className="flex items-start gap-4">
        <div className="p-3 rounded-lg bg-orange-500/20">
          <Sparkles className="h-6 w-6 text-orange-400" />
        </div>
        <div className="flex-1">
          <h3 className="text-lg font-semibold text-foreground mb-2">HubSpot Auto-Apply</h3>
          <p className="text-muted-foreground mb-4">
            Connect your HubSpot account to automatically apply SEO/GEO recommendations to
            your CMS pages.
          </p>
          <Button onClick={onConnect} className="bg-brand text-brand-foreground hover:bg-brand/90">
            <Sparkles className="h-4 w-4 mr-2" />
            Connect HubSpot
          </Button>
        </div>
      </div>
    </Card>
  );
}

function HubSpotConnectedCard({
  connections,
  pages,
  recommendations,
  applyResults,
  selection,
  status,
  onDisconnect,
  onConnectionChange,
  onPageChange,
  onApply,
}: {
  connections: HubSpotConnection[];
  pages: HubSpotPage[];
  recommendations: Recommendation[];
  applyResults: ApplyResult[];
  selection: { connectionId: string | null; pageId: string | null };
  status: { loading: boolean; applying: boolean };
  onDisconnect: () => void;
  onConnectionChange: (connectionId: string) => void;
  onPageChange: (pageId: string) => void;
  onApply: () => void;
}) {
  return (
    <Card className="glass-card p-6">
      <div className="flex items-start gap-4">
        <div className="p-3 rounded-lg bg-orange-500/20">
          <Sparkles className="h-6 w-6 text-orange-400" />
        </div>
        <div className="flex-1">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-lg font-semibold text-foreground">HubSpot Auto-Apply</h3>
            <div className="flex items-center gap-2">
              <Badge variant="outline" className="border-green-500/50 text-green-400">
                <CheckCircle2 className="h-3 w-3 mr-1" />
                Connected
              </Badge>
              <Button
                variant="ghost"
                size="sm"
                onClick={onDisconnect}
                className="h-6 px-2 text-xs"
                title="Disconnect to switch account"
              >
                <LogOut className="h-3 w-3" />
              </Button>
            </div>
          </div>

          <p className="text-muted-foreground mb-4">
            Apply AI-generated SEO/GEO recommendations directly to your HubSpot CMS pages.
          </p>

          <div className="space-y-4">
            <div>
              <label htmlFor="hubspot-portal" className="text-sm text-muted-foreground mb-2 block">
                HubSpot Portal
              </label>
              <select
                id="hubspot-portal"
                value={selection.connectionId || ""}
                onChange={(e) => onConnectionChange(e.target.value)}
                className="glass-input w-full px-4 py-2"
              >
                {connections.map((conn) => (
                  <option key={conn.id} value={conn.id}>
                    {conn.portal_id}
                  </option>
                ))}
              </select>
            </div>

            {status.loading && !pages.length ? (
              <div className="text-muted-foreground text-sm">Loading pages...</div>
            ) : (
              <div>
                <label htmlFor="hubspot-page" className="text-sm text-muted-foreground mb-2 block">
                  HubSpot Page
                </label>
                <select
                  id="hubspot-page"
                  value={selection.pageId || ""}
                  onChange={(e) => onPageChange(e.target.value)}
                  className="glass-input w-full px-4 py-2"
                  disabled={pages.length === 0}
                >
                  <option value="">Select a page...</option>
                  {pages.map((page) => (
                    <option key={page.id} value={page.hubspot_id}>
                      {page.title || page.url}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {selection.pageId && recommendations.length > 0 && (
              <div className="bg-muted/50 p-4 rounded-xl border border-border">
                <h4 className="text-sm font-semibold text-foreground mb-3">
                  {recommendations.length} Recommendation
                  {recommendations.length !== 1 ? "s" : ""} Available
                </h4>
                <div className="space-y-2 max-h-48 overflow-y-auto">
                  {recommendations.map((rec) => (
                    <div
                      key={rec.id}
                      className="text-xs bg-background/50 p-2 rounded border border-border"
                    >
                      <div className="font-medium text-foreground">{rec.issue_type}</div>
                      <div className="text-muted-foreground mt-1">
                        Field: {rec.field} • Priority: {rec.priority}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <Button
              onClick={onApply}
              disabled={!selection.pageId || recommendations.length === 0 || status.applying}
              className="w-full bg-brand text-brand-foreground hover:bg-brand/90"
            >
              {status.applying ? (
                <>
                  <Clock className="h-4 w-4 mr-2 animate-spin" />
                  Applying Changes...
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4 mr-2" />
                  Apply {recommendations.length} Recommendation
                  {recommendations.length !== 1 ? "s" : ""}
                </>
              )}
            </Button>

            {applyResults.length > 0 && (
              <div className="space-y-2">
                {applyResults.map((result) => (
                  <div
                    key={result.page_path || result.issue_code || result.error || JSON.stringify(result)}
                    className={`p-4 rounded-lg border ${
                      result.success
                        ? "bg-green-500/10 border-green-500/50"
                        : "bg-red-500/10 border-red-500/50"
                    }`}
                  >
                    {result.success ? (
                      <div className="flex items-center gap-2 text-green-400 font-medium">
                        <CheckCircle2 className="h-5 w-5" />
                        Successfully applied changes!
                      </div>
                    ) : (
                      <div className="flex items-start gap-2 text-red-400">
                        <XCircle className="h-5 w-5 mt-0.5" />
                        <div>
                          <div className="font-medium">Error Applying Changes</div>
                          <div className="text-sm text-foreground/70 mt-1">{result.error}</div>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </Card>
  );
}

export function HubSpotIntegration({
  auditId,
  auditUrl: _auditUrl,
}: HubSpotIntegrationProps) {
  const [hubspotData, setHubspotData] = useState<{
    connections: HubSpotConnection[];
    pages: HubSpotPage[];
    recommendations: Recommendation[];
    applyResults: ApplyResult[];
  }>({
    connections: [],
    pages: [],
    recommendations: [],
    applyResults: [],
  });
  const [selection, setSelection] = useState<{
    connectionId: string | null;
    pageId: string | null;
  }>({
    connectionId: null,
    pageId: null,
  });
  const [status, setStatus] = useState({ loading: false, applying: false });

  const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

  useEffect(() => {
    fetchConnections();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchConnections = async () => {
    try {
      const res = await fetchWithBackendAuth(`${backendUrl}/api/v1/hubspot/connections`);
      if (res.ok) {
        const data = await res.json();
        setHubspotData((prev) => ({ ...prev, connections: data }));
        if (data.length > 0) {
          setSelection((prev) => ({ ...prev, connectionId: data[0].id }));
          fetchPages(data[0].id);
        }
      }
    } catch (err) {
      console.error("Error fetching connections:", err);
    }
  };

  const fetchPages = async (connectionId: string) => {
    setStatus((prev) => ({ ...prev, loading: true }));
    try {
      const res = await fetchWithBackendAuth(`${backendUrl}/api/v1/hubspot/pages/${connectionId}`);
      if (res.ok) {
        const data = await res.json();
        setHubspotData((prev) => ({ ...prev, pages: data }));
      }
    } catch (err) {
      console.error("Error fetching pages:", err);
    } finally {
      setStatus((prev) => ({ ...prev, loading: false }));
    }
  };

  const fetchRecommendations = async (pageId: string) => {
    if (!pageId) return;

    setStatus((prev) => ({ ...prev, loading: true }));
    try {
      const res = await fetchWithBackendAuth(`${backendUrl}/api/v1/hubspot/recommendations/${auditId}`);
      if (res.ok) {
        const data = await res.json();
        const pageRecs = data.recommendations.filter(
          (rec: Recommendation) => rec.hubspot_page_id === pageId,
        );
        setHubspotData((prev) => ({ ...prev, recommendations: pageRecs }));
      }
    } catch (err) {
      console.error("Error fetching recommendations:", err);
    } finally {
      setStatus((prev) => ({ ...prev, loading: false }));
    }
  };

  const handleConnectionChange = (connectionId: string) => {
    setSelection({ connectionId, pageId: null });
    setHubspotData((prev) => ({ ...prev, recommendations: [] }));
    fetchPages(connectionId);
  };

  const handlePageChange = (pageId: string) => {
    setSelection((prev) => ({ ...prev, pageId }));
    setHubspotData((prev) => ({ ...prev, recommendations: [] }));
    if (pageId) {
      fetchRecommendations(pageId);
    }
  };

  const applyRecommendations = async () => {
    if (hubspotData.recommendations.length === 0) return;

    setStatus((prev) => ({ ...prev, applying: true }));
    setHubspotData((prev) => ({ ...prev, applyResults: [] }));

    try {
      const res = await fetchWithBackendAuth(`${backendUrl}/api/v1/hubspot/apply-recommendations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          audit_id: parseInt(auditId, 10),
          recommendations: hubspotData.recommendations,
        }),
      });

      const data = await res.json();

      if (res.ok) {
        setHubspotData((prev) => ({
          ...prev,
          applyResults: [
            ...(data.details?.applied || []).map((r: any) => ({ ...r, success: true })),
            ...(data.details?.failed || []).map((r: any) => ({ ...r, success: false })),
          ],
        }));
      } else {
        setHubspotData((prev) => ({
          ...prev,
          applyResults: [
            {
              success: false,
              page_id: selection.pageId || "",
              field: "all",
              error: data.detail || "Error applying recommendations",
            },
          ],
        }));
      }
    } catch (err: any) {
      setHubspotData((prev) => ({
        ...prev,
        applyResults: [
          {
            success: false,
            page_id: selection.pageId || "",
            field: "all",
            error: err.message,
          },
        ],
      }));
    } finally {
      setStatus((prev) => ({ ...prev, applying: false }));
    }
  };

  const connectHubSpot = async () => {
    try {
      const res = await fetchWithBackendAuth(`${backendUrl}/api/v1/hubspot/auth-url`);
      const data = await res.json();
      if (!res.ok || !data?.url) {
        throw new Error(data?.detail || "Failed to get HubSpot auth URL");
      }
      window.location.href = data.url;
    } catch (err) {
      console.error("Error starting HubSpot OAuth:", err);
    }
  };

  if (hubspotData.connections.length === 0) {
    return <HubSpotConnectCard onConnect={connectHubSpot} />;
  }

  return (
    <HubSpotConnectedCard
      connections={hubspotData.connections}
      pages={hubspotData.pages}
      recommendations={hubspotData.recommendations}
      applyResults={hubspotData.applyResults}
      selection={selection}
      status={status}
      onDisconnect={() => setHubspotData((prev) => ({ ...prev, connections: [] }))}
      onConnectionChange={handleConnectionChange}
      onPageChange={handlePageChange}
      onApply={applyRecommendations}
    />
  );
}
