"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  CheckCircle2,
  XCircle,
  Clock,
  ExternalLink,
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
}

export function HubSpotIntegration({
  auditId,
  auditUrl,
}: HubSpotIntegrationProps) {
  const [connections, setConnections] = useState<HubSpotConnection[]>([]);
  const [pages, setPages] = useState<HubSpotPage[]>([]);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [selectedConnection, setSelectedConnection] = useState<string | null>(
    null,
  );
  const [selectedPage, setSelectedPage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [applying, setApplying] = useState(false);
  const [applyResults, setApplyResults] = useState<ApplyResult[]>([]);

  const backendUrl =
    process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

  useEffect(() => {
    fetchConnections();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchConnections = async () => {
    try {
      const res = await fetchWithBackendAuth(
        `${backendUrl}/api/hubspot/connections`,
      );
      if (res.ok) {
        const data = await res.json();
        setConnections(data);
        if (data.length > 0) {
          setSelectedConnection(data[0].id);
          fetchPages(data[0].id);
        }
      }
    } catch (err) {
      console.error("Error fetching connections:", err);
    }
  };

  const fetchPages = async (connectionId: string) => {
    setLoading(true);
    try {
      const res = await fetchWithBackendAuth(
        `${backendUrl}/api/hubspot/pages/${connectionId}`,
      );
      if (res.ok) {
        const data = await res.json();
        setPages(data);
      }
    } catch (err) {
      console.error("Error fetching pages:", err);
    } finally {
      setLoading(false);
    }
  };

  const fetchRecommendations = async () => {
    if (!selectedPage) return;

    setLoading(true);
    try {
      const res = await fetchWithBackendAuth(
        `${backendUrl}/api/hubspot/recommendations/${auditId}`,
      );
      if (res.ok) {
        const data = await res.json();
        // Filter recommendations for selected page
        const pageRecs = data.recommendations.filter(
          (rec: Recommendation) => rec.hubspot_page_id === selectedPage,
        );
        setRecommendations(pageRecs);
      }
    } catch (err) {
      console.error("Error fetching recommendations:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (selectedPage) {
      fetchRecommendations();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedPage]);

  const handleConnectionChange = (connectionId: string) => {
    setSelectedConnection(connectionId);
    setSelectedPage(null);
    setRecommendations([]);
    fetchPages(connectionId);
  };

  const applyRecommendations = async () => {
    if (recommendations.length === 0) return;

    setApplying(true);
    setApplyResults([]);

    try {
      const res = await fetchWithBackendAuth(
        `${backendUrl}/api/hubspot/apply-recommendations`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            audit_id: parseInt(auditId),
            recommendations: recommendations,
          }),
        },
      );

      const data = await res.json();

      if (res.ok) {
        setApplyResults([
          ...(data.details?.applied || []).map((r: any) => ({
            ...r,
            success: true,
          })),
          ...(data.details?.failed || []).map((r: any) => ({
            ...r,
            success: false,
          })),
        ]);
      } else {
        setApplyResults([
          {
            success: false,
            page_id: selectedPage || "",
            field: "all",
            error: data.detail || "Error applying recommendations",
          },
        ]);
      }
    } catch (err: any) {
      setApplyResults([
        {
          success: false,
          page_id: selectedPage || "",
          field: "all",
          error: err.message,
        },
      ]);
    } finally {
      setApplying(false);
    }
  };

  const connectHubSpot = () => {
    window.location.href = `${backendUrl}/api/hubspot/auth-url`;
  };

  if (connections.length === 0) {
    return (
      <Card className="glass-card p-6">
        <div className="flex items-start gap-4">
          <div className="p-3 rounded-lg bg-orange-500/20">
            <Sparkles className="h-6 w-6 text-orange-400" />
          </div>
          <div className="flex-1">
            <h3 className="text-lg font-semibold text-foreground mb-2">
              HubSpot Auto-Apply
            </h3>
            <p className="text-muted-foreground mb-4">
              Connect your HubSpot account to automatically apply SEO/GEO
              recommendations to your CMS pages.
            </p>
            <Button
              onClick={connectHubSpot}
              className="bg-brand text-brand-foreground hover:bg-brand/90"
            >
              <Sparkles className="h-4 w-4 mr-2" />
              Connect HubSpot
            </Button>
          </div>
        </div>
      </Card>
    );
  }

  return (
    <Card className="glass-card p-6">
      <div className="flex items-start gap-4">
        <div className="p-3 rounded-lg bg-orange-500/20">
          <Sparkles className="h-6 w-6 text-orange-400" />
        </div>
        <div className="flex-1">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-lg font-semibold text-foreground">
              HubSpot Auto-Apply
            </h3>
            <div className="flex items-center gap-2">
              <Badge
                variant="outline"
                className="border-green-500/50 text-green-400"
              >
                <CheckCircle2 className="h-3 w-3 mr-1" />
                Connected
              </Badge>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setConnections([])}
                className="h-6 px-2 text-xs"
                title="Disconnect to switch account"
              >
                <LogOut className="h-3 w-3" />
              </Button>
            </div>
          </div>
          <p className="text-muted-foreground mb-4">
            Apply AI-generated SEO/GEO recommendations directly to your HubSpot
            CMS pages.
          </p>

          <div className="space-y-4">
            {/* Connection Selector */}
            <div>
              <label className="text-sm text-muted-foreground mb-2 block">
                HubSpot Portal
              </label>
              <select
                value={selectedConnection || ""}
                onChange={(e) => handleConnectionChange(e.target.value)}
                className="glass-input w-full px-4 py-2"
              >
                {connections.map((conn) => (
                  <option key={conn.id} value={conn.id}>
                    {conn.portal_id}
                  </option>
                ))}
              </select>
            </div>

            {/* Page Selector */}
            {loading && !pages.length ? (
              <div className="text-muted-foreground text-sm">
                Loading pages...
              </div>
            ) : (
              <div>
                <label className="text-sm text-muted-foreground mb-2 block">
                  HubSpot Page
                </label>
                <select
                  value={selectedPage || ""}
                  onChange={(e) => setSelectedPage(e.target.value)}
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

            {/* Recommendations Display */}
            {selectedPage && recommendations.length > 0 && (
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
                      <div className="font-medium text-foreground">
                        {rec.issue_type}
                      </div>
                      <div className="text-muted-foreground mt-1">
                        Field: {rec.field} • Priority: {rec.priority}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Apply Button */}
            <Button
              onClick={applyRecommendations}
              disabled={
                !selectedPage || recommendations.length === 0 || applying
              }
              className="w-full bg-brand text-brand-foreground hover:bg-brand/90"
            >
              {applying ? (
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

            {/* Results */}
            {applyResults.length > 0 && (
              <div className="space-y-2">
                {applyResults.map((result, idx) => (
                  <div
                    key={idx}
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
                          <div className="font-medium">
                            Error Applying Changes
                          </div>
                          <div className="text-sm text-foreground/70 mt-1">
                            {result.error}
                          </div>
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
