"use client";

import { useState, useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Header } from "@/components/header";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { withLocale } from "@/lib/locale-routing";
import {
  Loader2,
  FileText,
  Download,
  Eye,
  FileJson,
  CheckCircle,
  Clock,
  AlertCircle,
  ArrowLeft,
} from "lucide-react";

interface Audit {
  id: number;
  url: string;
  domain: string;
  status: string;
  created_at: string;
  completed_at?: string;
}

export default function ReportsExportsPage() {
  const router = useRouter();
  const pathname = usePathname();
  const [audits, setAudits] = useState<Audit[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedAudit, setSelectedAudit] = useState<number | null>(null);
  const [generatingPDF, setGeneratingPDF] = useState(false);
  const [viewingMarkdown, setViewingMarkdown] = useState(false);
  const [markdownContent, setMarkdownContent] = useState("");

  useEffect(() => {
    loadAudits();
  }, []);

  const loadAudits = async () => {
    try {
      const data = await api.getDashboardData();
      const completed = data.recent_audits.filter(
        (a: any) => a.status === "completed",
      );
      setAudits(completed);
    } catch (error) {
      console.error("Error loading audits:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleGeneratePDF = async (auditId: number) => {
    setGeneratingPDF(true);
    try {
      const result = await api.generatePDF(auditId);
      const message = result?.message || "PDF generated successfully.";
      alert(message);
    } catch (error) {
      console.error("Error generating PDF:", error);
      alert("Error generating PDF. Please try again.");
    } finally {
      setGeneratingPDF(false);
    }
  };

  const handleViewMarkdown = async (auditId: number) => {
    setViewingMarkdown(true);
    try {
      const result = await api.getMarkdownReport(auditId);
      setMarkdownContent(result.markdown);
      setSelectedAudit(auditId);
    } catch (error) {
      console.error("Error loading markdown:", error);
      alert("Error loading markdown report");
    } finally {
      setViewingMarkdown(false);
    }
  };

  const handleDownloadJSON = async (auditId: number) => {
    try {
      const data = await api.getJSONReport(auditId);
      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `audit-${auditId}-report.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error("Error downloading JSON:", error);
      alert("Error downloading JSON report");
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "completed":
        return <CheckCircle className="h-4 w-4 text-green-400" />;
      case "processing":
      case "running":
        return <Clock className="h-4 w-4 text-yellow-400 animate-pulse" />;
      default:
        return <AlertCircle className="h-4 w-4 text-red-400" />;
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-12 w-12 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (markdownContent) {
    return (
      <div className="min-h-screen p-6">
        <div className="max-w-5xl mx-auto">
          <div className="mb-6 flex items-center justify-between">
            <Button
              variant="ghost"
              onClick={() => {
                setMarkdownContent("");
                setSelectedAudit(null);
              }}
              className="text-muted-foreground hover:text-foreground hover:bg-muted/50"
            >
              <ArrowLeft className="h-4 w-4 mr-2" /> Back to Reporting Studio
            </Button>
            <Button
              onClick={() => {
                const blob = new Blob([markdownContent], {
                  type: "text/markdown",
                });
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = `audit-${selectedAudit}-report.md`;
                a.click();
                URL.revokeObjectURL(url);
              }}
              className="glass-button-primary"
            >
              <Download className="h-4 w-4 mr-2" /> Export Markdown
            </Button>
          </div>
          <Card className="glass-card p-8">
            <pre className="whitespace-pre-wrap text-sm text-foreground font-mono leading-relaxed">
              {markdownContent}
            </pre>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Header />

      <main className="max-w-7xl mx-auto px-6 py-12">
        <div className="mb-8 animate-fade-up">
          <h1 className="text-3xl md:text-4xl font-semibold tracking-tight">
            Reporting Studio
          </h1>
          <p className="text-muted-foreground mt-2 max-w-2xl">
            Generate board-ready exports and structured data packages from completed audits.
          </p>
        </div>

        {/* Reports Grid */}
        <div>
          {audits.length === 0 ? (
            <Card className="glass-card p-12 text-center animate-fade-up">
              <FileText className="h-16 w-16 text-muted-foreground/50 mx-auto mb-4" />
              <h3 className="text-xl font-semibold text-foreground mb-2">
                No Completed Audits
              </h3>
              <p className="text-muted-foreground mb-6">
                Finish at least one audit to unlock report generation.
              </p>
              <Button
                onClick={() => router.push(withLocale(pathname, "/"))}
                className="glass-button-primary"
              >
                Run New Audit
              </Button>
            </Card>
          ) : (
            <div className="grid gap-6">
              {audits.map((audit) => (
                <Card
                  key={audit.id}
                  className="glass-card p-6 hover:bg-muted/50 transition-all"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-2">
                        {getStatusIcon(audit.status)}
                        <h3 className="text-lg font-semibold text-foreground">
                          {audit.domain}
                        </h3>
                        <Badge
                          variant="outline"
                          className="text-xs border-border/70 bg-muted/40 text-muted-foreground"
                        >
                          #{audit.id}
                        </Badge>
                      </div>
                      <p className="text-sm text-muted-foreground mb-1">
                        {audit.url}
                      </p>
                      <p className="text-xs text-muted-foreground/80">
                        Completed:{" "}
                        {audit.completed_at
                          ? new Date(audit.completed_at).toLocaleString()
                          : "N/A"}
                      </p>
                    </div>

                    <div className="flex gap-2">
                      <Button
                        onClick={() => handleGeneratePDF(audit.id)}
                        disabled={generatingPDF}
                        className="glass-button-primary"
                        size="sm"
                      >
                        {generatingPDF ? (
                          <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        ) : (
                          <FileText className="h-4 w-4 mr-2" />
                        )}
                        Build PDF
                      </Button>

                      <Button
                        onClick={() => handleViewMarkdown(audit.id)}
                        disabled={viewingMarkdown}
                        variant="outline"
                        className="border-border/70 bg-muted/40 hover:bg-muted/60 text-foreground"
                        size="sm"
                      >
                        <Eye className="h-4 w-4 mr-2" />
                        Open Markdown
                      </Button>

                      <Button
                        onClick={() => handleDownloadJSON(audit.id)}
                        variant="outline"
                        className="border-border/70 bg-muted/40 hover:bg-muted/60 text-foreground"
                        size="sm"
                      >
                        <FileJson className="h-4 w-4 mr-2" />
                        Export JSON
                      </Button>

                      <Button
                        onClick={() =>
                          router.push(withLocale(pathname, `/audits/${audit.id}`))
                        }
                        variant="ghost"
                        className="text-muted-foreground hover:text-foreground hover:bg-muted/50"
                        size="sm"
                      >
                        Open Audit →
                      </Button>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
