"use client";

import { useState, useEffect, useRef } from "react";
import { useParams, usePathname, useRouter } from "next/navigation";
import { Header } from "@/components/header";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Github,
  GitPullRequest,
  CheckCircle2,
  XCircle,
  Clock,
  ExternalLink,
  ArrowLeft,
  AlertCircle,
} from "lucide-react";
import { API_URL } from "@/lib/api";
import { fetchWithBackendAuth } from "@/lib/backend-auth";
import { withLocale } from "@/lib/locale-routing";
import type {
  FixInputField,
  FixInputGroup,
  FixInputsResponse,
  FixInputChatResponse,
} from "@/lib/types";

type ChatStep = {
  id: string;
  groupId: string;
  issueCode: string;
  pagePath: string;
  required: boolean;
  prompt?: string;
  field: FixInputField;
  assistantMessage?: string;
  suggestedValue?: string;
  confidence?: string;
  loading?: boolean;
};

export default function GitHubAutoFixPage() {
  const params = useParams();
  const router = useRouter();
  const pathname = usePathname();
  const auditId = params.id as string;

  const [audit, setAudit] = useState<any>(null);
  const [connections, setConnections] = useState<any[]>([]);
  const [repositories, setRepositories] = useState<any[]>([]);
  const [selectedConnection, setSelectedConnection] = useState<string | null>(
    null,
  );
  const [selectedRepo, setSelectedRepo] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [reposLoading, setReposLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [prResult, setPrResult] = useState<any>(null);
  const [missingInputs, setMissingInputs] = useState<FixInputGroup[]>([]);
  const [missingInputsLoading, setMissingInputsLoading] = useState(false);
  const [inputsSaving, setInputsSaving] = useState(false);
  const [inputValues, setInputValues] = useState<
    Record<string, Record<string, string>>
  >({});
  const [chatSteps, setChatSteps] = useState<ChatStep[]>([]);
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [chatHistory, setChatHistory] = useState<
    Array<{ role: "user" | "assistant"; content: string }>
  >([]);
  const [stepError, setStepError] = useState<string | null>(null);
  const chatSectionRef = useRef<HTMLDivElement>(null);

  const backendUrl = API_URL;
  const hasMissingRequired = missingInputs.some((group) => group.required);

  const formatErrorMessage = (value: any) => {
    if (!value) return "Error creating PR";
    if (typeof value === "string") return value;
    if (value instanceof Error) return value.message;
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  };

  const safeParseJson = async (res: Response) => {
    try {
      return await res.json();
    } catch {
      return null;
    }
  };

  const buildChatSteps = (groups: FixInputGroup[]): ChatStep[] => {
    const requiredGroups = groups.filter((group) => group.required);
    const optionalGroups = groups.filter((group) => !group.required);
    const orderedGroups = [...requiredGroups, ...optionalGroups];

    const steps: ChatStep[] = [];
    orderedGroups.forEach((group) => {
      group.fields.forEach((field) => {
        steps.push({
          id: `${group.id}:${field.key}`,
          groupId: group.id,
          issueCode: group.issue_code,
          pagePath: group.page_path,
          required: Boolean(field.required || group.required),
          prompt: group.prompt,
          field,
        });
      });
    });
    return steps;
  };

  const initializeInputValues = (groups: FixInputGroup[]) => {
    const values: Record<string, Record<string, string>> = {};
    groups.forEach((group) => {
      values[group.id] = {};
      group.fields.forEach((field) => {
        values[group.id][field.key] = field.value ?? "";
      });
    });
    setInputValues(values);
  };

  useEffect(() => {
    fetchAudit();
    fetchMissingInputs();
    fetchConnections();
    // Intentional bootstrap on mount only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    initializeInputValues(missingInputs);
    setChatSteps(buildChatSteps(missingInputs));
    setCurrentStepIndex(0);
    setChatHistory([]);
    setStepError(null);
  }, [missingInputs]);

  const fetchAudit = async () => {
    try {
      const res = await fetchWithBackendAuth(
        `${backendUrl}/api/v1/audits/${auditId}`,
      );
      if (res.ok) {
        const data = await res.json();
        setAudit(data);
      }
    } catch (err) {
      console.error("Error fetching audit:", err);
    } finally {
      setLoading(false);
    }
  };

  const fetchMissingInputs = async () => {
    setMissingInputsLoading(true);
    try {
      const res = await fetchWithBackendAuth(
        `${backendUrl}/api/v1/github/fix-inputs/${auditId}`,
      );
      if (res.ok) {
        const data: FixInputsResponse = await res.json();
        setMissingInputs(data.missing_inputs || []);
      }
    } catch (err) {
      console.error("Error fetching missing inputs:", err);
    } finally {
      setMissingInputsLoading(false);
    }
  };

  const fetchConnections = async () => {
    try {
      const res = await fetchWithBackendAuth(
        `${backendUrl}/api/v1/github/connections`,
      );
      if (res.ok) {
        const data = await res.json();
        setConnections(data);
        if (data.length > 0) {
          setSelectedConnection(data[0].id);
          fetchRepositories(data[0].id);
        }
      }
    } catch (err) {
      console.error("Error fetching connections:", err);
    }
  };

  const fetchRepositories = async (connectionId: string) => {
    setReposLoading(true);
    try {
      const res = await fetchWithBackendAuth(
        `${backendUrl}/api/v1/github/repos/${connectionId}`,
      );
      if (res.ok) {
        const data = await res.json();
        setRepositories(data);
      }
    } catch (err) {
      console.error("Error fetching repositories:", err);
    } finally {
      setReposLoading(false);
    }
  };

  const handleConnectionChange = (connectionId: string) => {
    setSelectedConnection(connectionId);
    setSelectedRepo(null);
    fetchRepositories(connectionId);
  };

  const updateInputValue = (
    groupId: string,
    fieldKey: string,
    value: string,
  ) => {
    setInputValues((prev) => ({
      ...prev,
      [groupId]: {
        ...(prev[groupId] || {}),
        [fieldKey]: value,
      },
    }));
  };

  const fetchChatSuggestion = async (step: ChatStep, index: number) => {
    setChatSteps((prev) =>
      prev.map((s, i) => (i === index ? { ...s, loading: true } : s)),
    );
    try {
      const res = await fetchWithBackendAuth(
        `${backendUrl}/api/v1/github/fix-inputs/chat/${auditId}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            issue_code: step.issueCode,
            field_key: step.field.key,
            field_label: step.field.label,
            placeholder: step.field.placeholder,
            current_values: inputValues[step.groupId] || {},
            language: "en",
            history: chatHistory.slice(-6),
          }),
        },
      );
      if (res.ok) {
        const data: FixInputChatResponse = await res.json();
        setChatSteps((prev) =>
          prev.map((s, i) =>
            i === index
              ? {
                  ...s,
                  loading: false,
                  assistantMessage: data.assistant_message,
                  suggestedValue: data.suggested_value,
                  confidence: data.confidence,
                }
              : s,
          ),
        );
        if (data.assistant_message) {
          setChatHistory((prev) => [
            ...prev,
            { role: "assistant", content: data.assistant_message },
          ]);
        }
        return;
      }
    } catch (err) {
      console.error("Error fetching chat suggestion:", err);
    }
    setChatSteps((prev) =>
      prev.map((s, i) =>
        i === index
          ? {
              ...s,
              loading: false,
              assistantMessage:
                "Please provide the requested data based on your audited content.",
              suggestedValue: "",
              confidence: "unknown",
            }
          : s,
      ),
    );
  };

  const handleUseSuggestion = (step: ChatStep) => {
    if (!step.suggestedValue) return;
    updateInputValue(step.groupId, step.field.key, step.suggestedValue);
    setStepError(null);
  };

  const handleNextStep = (step: ChatStep) => {
    const value = (inputValues[step.groupId]?.[step.field.key] || "").trim();
    if (step.required && !value) {
      setStepError("This field is required to create the PR.");
      return;
    }
    setStepError(null);
    setChatHistory((prev) => [
      ...prev,
      { role: "user", content: value || "Skipped" },
    ]);
    setCurrentStepIndex((prev) => Math.min(prev + 1, chatSteps.length - 1));
  };

  const buildInputsPayload = () => {
    return missingInputs.map((group) => {
      const values: Record<string, any> = {};
      const groupValues = inputValues[group.id] || {};
      group.fields.forEach((field) => {
        values[field.key] = groupValues[field.key] ?? "";
      });

      if (group.issue_code?.toUpperCase().startsWith("FAQ_")) {
        const faqItems: Array<{ question: string; answer: string }> = [];
        for (let i = 1; i <= 3; i += 1) {
          const q = (values[`faq_q${i}`] || "").toString().trim();
          const a = (values[`faq_a${i}`] || "").toString().trim();
          if (q || a) {
            faqItems.push({ question: q, answer: a });
          }
        }
        return {
          id: group.id,
          issue_code: group.issue_code,
          page_path: group.page_path,
          values: { faq_items: faqItems },
        };
      }

      return {
        id: group.id,
        issue_code: group.issue_code,
        page_path: group.page_path,
        values,
      };
    });
  };

  useEffect(() => {
    const step = chatSteps[currentStepIndex];
    if (!step || step.assistantMessage || step.loading) return;
    fetchChatSuggestion(step, currentStepIndex);
    // Suggestions are intentionally fetched for the active step only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentStepIndex, chatSteps]);

  const saveFixInputs = async () => {
    setInputsSaving(true);
    try {
      const res = await fetchWithBackendAuth(
        `${backendUrl}/api/v1/github/fix-inputs/${auditId}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ inputs: buildInputsPayload() }),
        },
      );
      const data: FixInputsResponse = await res.json();
      if (res.ok) {
        setMissingInputs(data.missing_inputs || []);
      }
    } catch (err) {
      console.error("Error saving inputs:", err);
    } finally {
      setInputsSaving(false);
    }
  };

  const createAutoFixPR = async () => {
    if (!selectedConnection || !selectedRepo) return;

    setCreating(true);
    setPrResult(null);

    try {
      const res = await fetchWithBackendAuth(
        `${backendUrl}/api/v1/github/create-auto-fix-pr/${selectedConnection}/${selectedRepo}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ audit_id: parseInt(auditId) }),
        },
      );

      const data = await safeParseJson(res);

      if (res.ok) {
        setPrResult({ success: true, data });
      } else {
        if (res.status === 422 && data?.detail?.missing_inputs) {
          setMissingInputs(data.detail.missing_inputs || []);
          setPrResult({
            success: false,
            error: formatErrorMessage(
              data.detail.message || "Missing required inputs",
            ),
          });
          if (chatSectionRef.current) {
            chatSectionRef.current.scrollIntoView({
              behavior: "smooth",
              block: "start",
            });
          }
        } else {
          setPrResult({
            success: false,
            error: formatErrorMessage(
              data?.detail || data || "Error creating PR",
            ),
          });
        }
      }
    } catch (err: any) {
      setPrResult({ success: false, error: formatErrorMessage(err) });
    } finally {
      setCreating(false);
    }
  };

  const connectGitHub = async () => {
    try {
      const res = await fetchWithBackendAuth(`${backendUrl}/api/v1/github/auth-url`);
      const data = await safeParseJson(res);
      if (!res.ok || !data?.url) {
        throw new Error(data?.detail || "Failed to get GitHub auth URL");
      }
      window.location.href = data.url;
    } catch (err) {
      console.error("Error starting GitHub OAuth:", err);
      setPrResult({
        success: false,
        error: formatErrorMessage(err),
      });
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-screen flex-col">
        <Header />
        <main className="flex-1 flex items-center justify-center">
          <Clock className="h-8 w-8 animate-spin text-muted-foreground" />
        </main>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col pb-20 bg-background text-foreground">
      <Header />

      <main className="flex-1 container mx-auto px-6 py-8">
        {/* Back button */}
        <Button
          variant="ghost"
          onClick={() => router.push(withLocale(pathname, `/audits/${auditId}`))}
          className="mb-8 text-muted-foreground hover:text-foreground hover:bg-muted/50 pl-0"
        >
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Audit Summary
        </Button>

        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl md:text-4xl font-semibold tracking-tight mb-2">
            GitHub Delivery Agent
          </h1>
          <p className="text-muted-foreground">
            Translate audit findings into implementation-ready pull requests for your repository.
          </p>
        </div>

        {/* No GitHub connection */}
        {connections.length === 0 && (
          <Card className="glass-card p-12 border border-border text-center">
            <div className="max-w-md mx-auto">
              <div className="mb-6 flex justify-center">
                <div className="p-6 rounded-full bg-brand/10">
                  <Github className="h-12 w-12 text-brand" />
                </div>
              </div>
              <h2 className="text-2xl font-semibold text-foreground mb-4">
                Connect GitHub
              </h2>
              <p className="text-muted-foreground mb-8">
                Connect your GitHub account to enable PR generation from validated SEO/GEO findings.
              </p>
              <Button
                onClick={connectGitHub}
                className="bg-brand text-brand-foreground hover:bg-brand/90 px-8 py-6 text-lg"
              >
                <Github className="h-5 w-5 mr-2" />
                Connect GitHub Workspace
              </Button>
            </div>
          </Card>
        )}

        {/* GitHub connected */}
        {connections.length > 0 && (
          <div className="space-y-6">
            {/* Connection Info */}
            <Card className="glass-card p-6 border border-border">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className="p-3 rounded-lg bg-emerald-500/10">
                    <CheckCircle2 className="h-6 w-6 text-emerald-500" />
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold text-foreground">
                      GitHub Connected
                    </h3>
                    <p className="text-sm text-muted-foreground">
                      Active identity{" "}
                      <span className="text-foreground font-medium">
                        {connections[0].github_username}
                      </span>
                    </p>
                  </div>
                </div>
                <Badge className="border-emerald-500/30 text-emerald-600 bg-emerald-500/10">
                  Active
                </Badge>
              </div>
            </Card>

            {/* Configuration */}
            <Card className="glass-card p-8 border border-border">
              <h3 className="text-xl font-semibold text-foreground mb-6">
                Configure Delivery
              </h3>

              <div className="space-y-6">
                {/* Connection Selector */}
                <div>
                  <label className="block text-sm font-medium text-muted-foreground mb-3">
                    Source Account
                  </label>
                  <select
                    value={selectedConnection || ""}
                    onChange={(e) => handleConnectionChange(e.target.value)}
                    className="glass-input w-full px-4 py-3"
                  >
                    {connections.map((conn) => (
                      <option
                        key={conn.id}
                        value={conn.id}
                        className="bg-gray-900"
                      >
                        {conn.github_username}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Repository Selector */}
                <div>
                  <label className="block text-sm font-medium text-muted-foreground mb-3">
                    Target Repository
                  </label>
                  {reposLoading ? (
                    <div className="flex items-center gap-2 text-muted-foreground py-3">
                      <Clock className="h-4 w-4 animate-spin" />
                      Loading repositories...
                    </div>
                  ) : repositories.length === 0 ? (
                    <div className="flex items-center gap-2 text-muted-foreground py-3">
                      <AlertCircle className="h-4 w-4" />
                      No repositories found. Sync repositories first.
                    </div>
                  ) : (
                    <select
                      value={selectedRepo || ""}
                      onChange={(e) => setSelectedRepo(e.target.value)}
                      className="glass-input w-full px-4 py-3"
                    >
                      <option value="" className="bg-gray-900">
                        Select repository...
                      </option>
                      {repositories.map((repo) => (
                        <option
                          key={repo.id}
                          value={repo.id}
                          className="bg-gray-900"
                        >
                          {repo.full_name} ({repo.site_type || "unknown"})
                        </option>
                      ))}
                    </select>
                  )}
                </div>

                {/* What will be fixed */}
                {audit && (
                  <div className="glass-panel border border-border rounded-xl p-6">
                    <h4 className="text-sm font-semibold text-foreground mb-4">
                      Planned issue scope
                    </h4>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      <div className="bg-muted/50 p-4 rounded-lg border border-border">
                        <div className="text-2xl font-bold text-red-500 mb-1">
                          {audit.critical_issues || 0}
                        </div>
                        <div className="text-xs text-muted-foreground">
                          Critical issues
                        </div>
                      </div>
                      <div className="bg-muted/50 p-4 rounded-lg border border-border">
                        <div className="text-2xl font-bold text-orange-500 mb-1">
                          {audit.high_issues || 0}
                        </div>
                        <div className="text-xs text-muted-foreground">
                          High-priority issues
                        </div>
                      </div>
                      <div className="bg-muted/50 p-4 rounded-lg border border-border">
                        <div className="text-2xl font-bold text-amber-500 mb-1">
                          {audit.medium_issues || 0}
                        </div>
                        <div className="text-xs text-muted-foreground">
                          Medium-priority issues
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* Guided chat for missing inputs */}
                <div
                  ref={chatSectionRef}
                  className="glass-panel border border-border rounded-xl p-6 space-y-4"
                >
                  <div>
                    <h4 className="text-sm font-semibold text-foreground">
                      Guided Inputs (Kimi)
                    </h4>
                    <p className="text-xs text-muted-foreground mt-1">
                      Kimi proposes audit-grounded values. Required fields must be saved before PR creation.
                    </p>
                  </div>

                  {missingInputsLoading ? (
                    <div className="flex items-center gap-2 text-muted-foreground">
                      <Clock className="h-4 w-4 animate-spin" />
                      Loading required inputs...
                    </div>
                  ) : missingInputs.length === 0 ? (
                    <div className="text-sm text-emerald-600">
                      All required inputs are complete. You can generate the PR.
                    </div>
                  ) : (
                    <div className="space-y-6">
                      {chatSteps
                        .slice(0, currentStepIndex + 1)
                        .map((step, index) => {
                          const value = (
                            inputValues[step.groupId]?.[step.field.key] || ""
                          ).trim();
                          const isActive = index === currentStepIndex;
                          return (
                            <div
                              key={step.id}
                              className="rounded-lg border border-border/70 bg-background/60 p-4"
                            >
                              <div className="flex items-start justify-between gap-3">
                                <div>
                                  <p className="text-xs text-muted-foreground">
                                    {step.issueCode.replace(/_/g, " ")} ·{" "}
                                    {step.pagePath}
                                  </p>
                                  <p className="text-sm font-semibold text-foreground mt-1">
                                    {step.field.label}
                                  </p>
                                  {step.prompt && (
                                    <p className="text-xs text-muted-foreground mt-1">
                                      {step.prompt}
                                    </p>
                                  )}
                                </div>
                                {step.required && (
                                  <Badge className="border-red-500/30 text-red-500 bg-red-500/10">
                                    Required
                                  </Badge>
                                )}
                              </div>

                              <div className="mt-4 flex items-start gap-3">
                                <div className="h-9 w-9 rounded-full bg-brand/15 flex items-center justify-center text-xs font-semibold text-brand">
                                  K
                                </div>
                                <div className="space-y-2 flex-1">
                                  {step.loading ? (
                                    <div className="flex items-center gap-2 text-muted-foreground text-sm">
                                      <Clock className="h-4 w-4 animate-spin" />
                                      Generating suggestion...
                                    </div>
                                  ) : (
                                    <p className="text-sm text-foreground">
                                      {step.assistantMessage ||
                                        "Please provide the requested data based on your audited content."}
                                    </p>
                                  )}

                                  {step.suggestedValue && (
                                    <div className="rounded-md border border-border/60 bg-muted/40 p-3">
                                      <p className="text-xs text-muted-foreground mb-2">
                                        Suggested value
                                      </p>
                                      <p className="text-sm text-foreground break-words">
                                        {step.suggestedValue}
                                      </p>
                                      {isActive && (
                                        <Button
                                          variant="outline"
                                          size="sm"
                                          onClick={() =>
                                            handleUseSuggestion(step)
                                          }
                                          className="mt-2"
                                        >
                                          Apply suggestion
                                        </Button>
                                      )}
                                    </div>
                                  )}
                                </div>
                              </div>

                              {isActive ? (
                                <div className="mt-4 space-y-3">
                                  {step.field.input_type === "textarea" ? (
                                    <Textarea
                                      value={
                                        inputValues[step.groupId]?.[
                                          step.field.key
                                        ] || ""
                                      }
                                      onChange={(e) =>
                                        updateInputValue(
                                          step.groupId,
                                          step.field.key,
                                          e.target.value,
                                        )
                                      }
                                      placeholder={step.field.placeholder || ""}
                                      className="min-h-[88px] bg-background"
                                    />
                                  ) : (
                                    <Input
                                      value={
                                        inputValues[step.groupId]?.[
                                          step.field.key
                                        ] || ""
                                      }
                                      onChange={(e) =>
                                        updateInputValue(
                                          step.groupId,
                                          step.field.key,
                                          e.target.value,
                                        )
                                      }
                                      placeholder={step.field.placeholder || ""}
                                      className="bg-background"
                                    />
                                  )}
                                  {stepError && (
                                    <p className="text-xs text-red-500">
                                      {stepError}
                                    </p>
                                  )}
                                  <div className="flex flex-wrap items-center gap-2">
                                    <Button
                                      onClick={() => handleNextStep(step)}
                                      className="bg-foreground text-background hover:bg-foreground/90"
                                    >
                                      {index === chatSteps.length - 1
                                        ? "Finish Step"
                                        : "Next Step"}
                                    </Button>
                                  </div>
                                </div>
                              ) : (
                                <div className="mt-4 text-xs text-muted-foreground">
                                  Saved response: {value || "Skipped"}
                                </div>
                              )}
                            </div>
                          );
                        })}

                      {chatSteps.length > 0 &&
                        currentStepIndex >= chatSteps.length - 1 && (
                          <Button
                            onClick={saveFixInputs}
                            disabled={inputsSaving}
                            className="bg-foreground text-background hover:bg-foreground/90"
                          >
                            {inputsSaving ? (
                              <>
                                <Clock className="h-4 w-4 mr-2 animate-spin" />
                                Saving inputs...
                              </>
                            ) : (
                              "Save Inputs"
                            )}
                          </Button>
                        )}
                    </div>
                  )}
                </div>

                {/* Create PR Button */}
                <Button
                  onClick={createAutoFixPR}
                  disabled={!selectedRepo || creating || hasMissingRequired}
                  className="w-full bg-brand text-brand-foreground hover:bg-brand/90 py-6 text-lg font-semibold disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {creating ? (
                    <>
                      <Clock className="h-5 w-5 mr-2 animate-spin" />
                      Creating pull request...
                    </>
                  ) : (
                    <>
                      <GitPullRequest className="h-5 w-5 mr-2" />
                      Create Delivery PR
                    </>
                  )}
                </Button>
              </div>
            </Card>

            {/* Result */}
            {prResult && (
              <Card
                className={`p-6 border ${
                  prResult.success
                    ? "bg-emerald-500/10 border-emerald-500/30"
                    : "bg-red-500/10 border-red-500/30"
                }`}
              >
                {prResult.success ? (
                  <div className="space-y-4">
                    <div className="flex items-center gap-3">
                      <CheckCircle2 className="h-8 w-8 text-emerald-500" />
                      <div>
                        <h3 className="text-xl font-bold text-emerald-600">
                          Pull Request Created
                        </h3>
                        <p className="text-muted-foreground mt-1">
                          {prResult.data.files_modified} files updated with{" "}
                          {prResult.data.fixes_applied} generated fixes
                        </p>
                      </div>
                    </div>

                    {prResult.data.pr?.html_url && (
                      <div className="pt-4 border-t border-border/70">
                        <Button
                          onClick={() =>
                            window.open(prResult.data.pr.html_url, "_blank")
                          }
                          className="bg-emerald-600 hover:bg-emerald-700 text-white"
                        >
                          <ExternalLink className="h-4 w-4 mr-2" />
                          Open Pull Request
                        </Button>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="flex items-start gap-3">
                    <XCircle className="h-8 w-8 text-red-500 flex-shrink-0 mt-1" />
                    <div>
                      <h3 className="text-xl font-bold text-red-500 mb-2">
                        Pull Request Creation Failed
                      </h3>
                      <p className="text-muted-foreground">{prResult.error}</p>
                    </div>
                  </div>
                )}
              </Card>
            )}
          </div>
        )}
      </main>
    </div>
  );
}

