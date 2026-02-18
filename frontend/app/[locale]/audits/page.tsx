"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useUser } from "@auth0/nextjs-auth0/client";
import { Header } from "@/components/header";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { API_URL } from "@/lib/api";
import { fetchWithBackendAuth } from "@/lib/backend-auth";
import {
  RefreshCw,
  Globe,
  Clock,
  ArrowRight,
  Plus,
  Search,
  Filter,
  ChevronDown,
} from "lucide-react";

interface Audit {
  id: number;
  url: string;
  domain: string;
  status: string;
  created_at: string;
  geo_score?: number;
  total_pages?: number;
}

export default function AuditsListPage() {
  const router = useRouter();
  const { user } = useUser();
  const [audits, setAudits] = useState<Audit[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<
    "all" | "completed" | "running" | "pending" | "failed"
  >("all");
  const [searchQuery, setSearchQuery] = useState("");

  const backendUrl = API_URL;

  useEffect(() => {
    const fetchAudits = async () => {
      try {
        const response = await fetchWithBackendAuth(`${backendUrl}/api/audits`);
        const data = await response.json();
        setAudits(Array.isArray(data) ? data : []);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchAudits();
  }, [backendUrl, user]);

  const deleteAudit = async (auditId: number) => {
    const confirmed = window.confirm(
      `Delete audit #${auditId}? This action cannot be undone.`,
    );
    if (!confirmed) return;
    try {
      const res = await fetchWithBackendAuth(
        `${backendUrl}/api/audits/${auditId}`,
        { method: "DELETE" },
      );
      if (!res.ok) throw new Error(`Failed to delete audit: ${res.status}`);
      setAudits((prev) => prev.filter((a) => a.id !== auditId));
    } catch (err) {
      console.error(err);
      alert("Failed to delete the audit.");
    }
  };

  const filteredAudits = audits
    .filter((audit) => filter === "all" || audit.status === filter)
    .filter(
      (audit) =>
        audit.url.toLowerCase().includes(searchQuery.toLowerCase()) ||
        audit.domain?.toLowerCase().includes(searchQuery.toLowerCase()),
    )
    .sort(
      (a, b) =>
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
    );

  const getStatusColor = (status: string) => {
    switch (status) {
      case "completed":
        return "bg-emerald-500/10 text-emerald-600 border-emerald-500/20";
      case "running":
        return "bg-amber-500/10 text-amber-600 border-amber-500/20";
      case "failed":
        return "bg-red-500/10 text-red-600 border-red-500/20";
      default:
        return "bg-muted/60 text-muted-foreground border-border/60";
    }
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Header />

      <main className="max-w-6xl mx-auto px-6 py-12">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
          <div>
            <h1 className="text-3xl font-bold">Your Audits</h1>
            <p className="text-muted-foreground mt-1">
              {audits.length} total audits
            </p>
          </div>
          <div className="flex gap-3">
            <Button
              variant="outline"
              size="sm"
              onClick={() => window.location.reload()}
            >
              <RefreshCw className="h-4 w-4 mr-2" /> Refresh
            </Button>
            <Button onClick={() => router.push("/")}>
              <Plus className="h-4 w-4 mr-2" /> New Audit
            </Button>
          </div>
        </div>

        {/* Filters */}
        <div className="flex flex-col md:flex-row gap-4 mb-8">
          <div className="relative flex-1">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search audits..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-12 pr-4 py-3 glass-panel border border-border rounded-xl text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-border/80"
            />
          </div>
          <div className="flex gap-2">
            {(
              ["all", "completed", "running", "pending", "failed"] as const
            ).map((status) => (
              <button
                key={status}
                onClick={() => setFilter(status)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors capitalize ${
                  filter === status
                    ? "bg-muted text-foreground"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
                }`}
              >
                {status === "running" ? "processing" : status}
              </button>
            ))}
          </div>
        </div>

        {/* Loading */}
        {loading && (
          <div className="flex items-center justify-center py-20">
            <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        )}

        {/* Audits Grid */}
        {!loading && filteredAudits.length > 0 && (
          <div className="grid gap-4">
            {filteredAudits.map((audit) => (
              <div
                key={audit.id}
                onClick={() => router.push(`/audits/${audit.id}`)}
                className="group p-6 glass-card border border-border rounded-2xl cursor-pointer hover:bg-muted/50 hover:border-border/80 transition-all"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className="p-3 bg-muted/50 rounded-xl">
                      <Globe className="w-6 h-6 text-brand" />
                    </div>
                    <div>
                      <h3 className="text-lg font-medium group-hover:text-brand transition-colors">
                        {audit.domain ||
                          (() => {
                            try {
                              return new URL(audit.url).hostname.replace(
                                "www.",
                                "",
                              );
                            } catch {
                              return audit.url;
                            }
                          })()}
                      </h3>
                      <p className="text-sm text-muted-foreground mt-1">
                        {audit.url}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-4">
                    {audit.status === "completed" && audit.geo_score && (
                      <div className="text-right hidden md:block">
                        <p className="text-sm text-muted-foreground">
                          GEO Score
                        </p>
                        <p className="text-lg font-semibold text-emerald-600">
                          {Math.round(audit.geo_score)}%
                        </p>
                      </div>
                    )}

                    <Badge
                      variant="outline"
                      className={getStatusColor(audit.status)}
                    >
                      {audit.status === "running" ? "processing" : audit.status}
                    </Badge>

                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-red-400 hover:text-red-300 hover:bg-red-500/10"
                      onClick={(e) => {
                        e.stopPropagation();
                        deleteAudit(audit.id);
                      }}
                    >
                      Delete
                    </Button>

                    <div className="text-right hidden md:block">
                      <p className="text-sm text-muted-foreground">Created</p>
                      <p className="text-sm text-foreground flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {new Date(audit.created_at).toLocaleDateString()}
                      </p>
                    </div>

                    <ArrowRight className="w-5 h-5 text-muted-foreground group-hover:text-foreground transition-colors" />
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Empty State */}
        {!loading && filteredAudits.length === 0 && (
          <div className="text-center py-20">
            <Globe className="w-16 h-16 text-muted-foreground/50 mx-auto mb-6" />
            <h3 className="text-xl font-medium text-muted-foreground mb-2">
              {searchQuery || filter !== "all"
                ? "No audits found"
                : "No audits yet"}
            </h3>
            <p className="text-muted-foreground/70 mb-6">
              {searchQuery || filter !== "all"
                ? "Try adjusting your search or filters"
                : "Start your first GEO audit to see results here"}
            </p>
            <Button onClick={() => router.push("/")}>
              <Plus className="w-4 h-4 mr-2" />
              Start New Audit
            </Button>
          </div>
        )}
      </main>
    </div>
  );
}
