"use client";

/**
 * HubSpot Integration - Frontend Component Example
 * Componente para aplicar recomendaciones SEO directamente a HubSpot
 */

import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  CheckCircle,
  XCircle,
  AlertTriangle,
  ExternalLink,
  Zap,
} from "lucide-react";
import { API_URL } from "@/lib/api";
import { fetchWithBackendAuth } from "@/lib/backend-auth";

interface HubSpotRecommendation {
  id: string;
  hubspot_page_id: string;
  page_url: string;
  page_title: string;
  field: "meta_description" | "html_title" | "alt_text" | "content";
  current_value: string | null;
  recommended_value: string;
  priority: "high" | "medium" | "low";
  auto_fixable: boolean;
  issue_type: string;
}

interface ApplyResult {
  success: boolean;
  page_id: string;
  error?: string;
}

export default function HubSpotApplyRecommendations({
  auditId,
}: {
  auditId: string;
}) {
  const [recommendations, setRecommendations] = useState<
    HubSpotRecommendation[]
  >([]);
  const [selectedRecs, setSelectedRecs] = useState<Set<string>>(new Set());
  const [applying, setApplying] = useState(false);
  const [results, setResults] = useState<ApplyResult[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchRecommendations = useCallback(async () => {
    try {
      const response = await fetchWithBackendAuth(
        `${API_URL}/api/hubspot/recommendations/${auditId}`,
      );
      const data = await response.json();
      setRecommendations(data.recommendations);

      // Auto-select all auto-fixable recommendations
      const autoFixable = new Set<string>(
        data.recommendations
          .filter((r: HubSpotRecommendation) => r.auto_fixable)
          .map((r: HubSpotRecommendation) => r.id),
      );
      setSelectedRecs(autoFixable);
    } catch (error) {
      console.error("Error fetching recommendations:", error);
    } finally {
      setLoading(false);
    }
  }, [auditId]);

  useEffect(() => {
    fetchRecommendations();
  }, [fetchRecommendations]);

  const toggleRecommendation = (id: string) => {
    const newSelected = new Set(selectedRecs);
    if (newSelected.has(id)) {
      newSelected.delete(id);
    } else {
      newSelected.add(id);
    }
    setSelectedRecs(newSelected);
  };

  const selectAll = (type: "all" | "auto" | "none") => {
    if (type === "none") {
      setSelectedRecs(new Set());
    } else if (type === "all") {
      setSelectedRecs(new Set(recommendations.map((r) => r.id)));
    } else if (type === "auto") {
      setSelectedRecs(
        new Set(recommendations.filter((r) => r.auto_fixable).map((r) => r.id)),
      );
    }
  };

  const applyRecommendations = async () => {
    setApplying(true);
    setResults([]);

    try {
      const selectedRecommendations = recommendations.filter((r) =>
        selectedRecs.has(r.id),
      );

      const response = await fetchWithBackendAuth(
        `${API_URL}/api/hubspot/apply-recommendations`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            audit_id: auditId,
            recommendations: selectedRecommendations,
          }),
        },
      );

      const data = await response.json();
      setResults(data.details.applied.concat(data.details.failed));

      // Show success message
      alert(`✅ Applied ${data.applied} changes successfully!`);

      // Reload recommendations to show updated state
      await fetchRecommendations();
    } catch (error) {
      console.error("Error applying recommendations:", error);
      alert("❌ Error applying recommendations");
    } finally {
      setApplying(false);
    }
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case "high":
        return "bg-red-500";
      case "medium":
        return "bg-yellow-500";
      case "low":
        return "bg-brand";
      default:
        return "bg-gray-500";
    }
  };

  const getFieldLabel = (field: string) => {
    const labels: Record<string, string> = {
      meta_description: "Meta Description",
      html_title: "Title Tag",
      alt_text: "Alt Text",
      content: "Content",
    };
    return labels[field] || field;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-muted-foreground">Loading recommendations...</p>
        </div>
      </div>
    );
  }

  const stats = {
    total: recommendations.length,
    selected: selectedRecs.size,
    autoFixable: recommendations.filter((r) => r.auto_fixable).length,
    high: recommendations.filter((r) => r.priority === "high").length,
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Apply Changes to HubSpot</h1>
          <p className="text-muted-foreground mt-2">
            Apply SEO recommendations directly to your HubSpot pages
          </p>
        </div>
        <Badge variant="outline" className="text-lg px-4 py-2">
          <Zap className="w-4 h-4 mr-2" />
          {stats.autoFixable} Auto-fixable
        </Badge>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Issues
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.total}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Selected
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-brand">
              {stats.selected}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Auto-fixable
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {stats.autoFixable}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              High Priority
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">{stats.high}</div>
          </CardContent>
        </Card>
      </div>

      {/* Action Buttons */}
      <div className="flex items-center gap-3">
        <Button onClick={() => selectAll("auto")} variant="outline">
          Select Auto-fixable
        </Button>
        <Button onClick={() => selectAll("all")} variant="outline">
          Select All
        </Button>
        <Button onClick={() => selectAll("none")} variant="outline">
          Clear Selection
        </Button>

        <div className="ml-auto">
          <Button
            onClick={applyRecommendations}
            disabled={selectedRecs.size === 0 || applying}
            size="lg"
            className="px-8"
          >
            {applying ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2" />
                Applying...
              </>
            ) : (
              <>
                <CheckCircle className="w-4 h-4 mr-2" />
                Apply {selectedRecs.size} Changes
              </>
            )}
          </Button>
        </div>
      </div>

      {/* Recommendations List */}
      <div className="space-y-3">
        {recommendations.map((rec) => {
          const isSelected = selectedRecs.has(rec.id);
          const wasApplied = results.find(
            (r) => r.page_id === rec.hubspot_page_id,
          );

          return (
            <Card
              key={rec.id}
              className={`transition-all cursor-pointer hover:shadow-md ${
                isSelected ? "ring-2 ring-primary" : ""
              } ${wasApplied?.success ? "bg-green-50" : ""}`}
              onClick={() => toggleRecommendation(rec.id)}
            >
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => toggleRecommendation(rec.id)}
                        className="w-4 h-4"
                        onClick={(e) => e.stopPropagation()}
                      />
                      <CardTitle className="text-lg">
                        {rec.page_title}
                      </CardTitle>
                      <Badge className={getPriorityColor(rec.priority)}>
                        {rec.priority}
                      </Badge>
                      {rec.auto_fixable && (
                        <Badge variant="outline" className="bg-green-50">
                          <Zap className="w-3 h-3 mr-1" />
                          Auto-fix
                        </Badge>
                      )}
                      {wasApplied && (
                        <Badge
                          variant={
                            wasApplied.success ? "default" : "destructive"
                          }
                        >
                          {wasApplied.success ? (
                            <>
                              <CheckCircle className="w-3 h-3 mr-1" />
                              Aplicado
                            </>
                          ) : (
                            <>
                              <XCircle className="w-3 h-3 mr-1" />
                              Error
                            </>
                          )}
                        </Badge>
                      )}
                    </div>
                    <CardDescription className="flex items-center gap-2">
                      <span>{getFieldLabel(rec.field)}</span>
                      <span>•</span>
                      <a
                        href={rec.page_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-600 hover:underline flex items-center gap-1"
                        onClick={(e) => e.stopPropagation()}
                      >
                        {rec.page_url}
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    </CardDescription>
                  </div>
                </div>
              </CardHeader>

              <CardContent>
                <div className="space-y-3">
                  {/* Current Value */}
                  <div>
                    <div className="text-sm font-medium text-muted-foreground mb-1">
                      Valor Actual:
                    </div>
                    <div className="text-sm bg-red-50 border border-red-200 rounded p-2">
                      {rec.current_value || (
                        <span className="text-muted-foreground italic">
                          (empty)
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Recommended Value */}
                  <div>
                    <div className="text-sm font-medium text-muted-foreground mb-1">
                      Valor Recomendado:
                    </div>
                    <div className="text-sm bg-green-50 border border-green-200 rounded p-2">
                      {rec.recommended_value}
                    </div>
                  </div>

                  {/* Issue Type */}
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <AlertTriangle className="w-4 h-4" />
                    <span>{rec.issue_type}</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {recommendations.length === 0 && (
        <Card>
          <CardContent className="text-center py-12">
            <CheckCircle className="w-12 h-12 text-green-500 mx-auto mb-4" />
            <h3 className="text-lg font-semibold mb-2">
              Everything is optimized!
            </h3>
            <p className="text-muted-foreground">
              No pending recommendations to apply to HubSpot
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
