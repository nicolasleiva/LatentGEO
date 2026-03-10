"use client";

import { useState } from "react";
import { Header } from "@/components/header";
import { api } from "@/lib/api-client";
import type { AIContentSuggestion } from "@/lib/types";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { FileText, HelpCircle, Loader2, Sparkles } from "lucide-react";

type AIContentPageClientProps = {
  auditId: string;
  initialDomain: string;
  initialSuggestions: AIContentSuggestion[];
};

export default function AIContentPageClient({
  auditId,
  initialDomain,
  initialSuggestions,
}: AIContentPageClientProps) {
  const [form, setForm] = useState({ domain: initialDomain, topics: "" });
  const [loading, setLoading] = useState(false);
  const [suggestions, setSuggestions] =
    useState<AIContentSuggestion[]>(initialSuggestions);
  const [error, setError] = useState("");

  async function handleGenerate() {
    if (!form.domain || !form.topics) return;

    setLoading(true);
    setError("");

    try {
      const topicList = form.topics
        .split(",")
        .map((topic) => topic.trim())
        .filter(Boolean);
      const newSuggestions = await api.generateAIContent(
        auditId,
        form.domain,
        topicList,
      );
      setSuggestions((previous) => [...newSuggestions, ...previous]);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Failed to generate suggestions. Ensure Kimi/NVIDIA key is set.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Header />
      <main className="mx-auto max-w-6xl space-y-8 px-6 py-12">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight md:text-4xl">
              AI Content Strategy
            </h1>
            <p className="mt-2 text-muted-foreground">
              Generate content gaps, FAQs, and outlines to improve topical
              authority.
            </p>
          </div>
        </div>

        <Card className="glass-card">
          <CardHeader>
            <CardTitle>Generate Suggestions</CardTitle>
            <CardDescription>
              Analyze your domain against specific topics using AI.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <label
                  htmlFor="ai-content-domain"
                  className="text-sm font-medium"
                >
                  Domain
                </label>
                <Input
                  id="ai-content-domain"
                  className="glass-input"
                  placeholder="example.com"
                  value={form.domain}
                  onChange={(event) =>
                    setForm((previous) => ({
                      ...previous,
                      domain: event.target.value,
                    }))
                  }
                />
              </div>
              <div className="space-y-2">
                <label
                  htmlFor="ai-content-topics"
                  className="text-sm font-medium"
                >
                  Target Topics (comma separated)
                </label>
                <Input
                  id="ai-content-topics"
                  className="glass-input"
                  placeholder="e.g. cloud computing, devops"
                  value={form.topics}
                  onChange={(event) =>
                    setForm((previous) => ({
                      ...previous,
                      topics: event.target.value,
                    }))
                  }
                />
              </div>
            </div>
            <Button
              onClick={handleGenerate}
              disabled={loading}
              className="glass-button-primary w-full md:w-auto"
            >
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Analyzing Content...
                </>
              ) : (
                <>
                  <Sparkles className="mr-2 h-4 w-4" />
                  Generate Strategy
                </>
              )}
            </Button>
            {error ? <p className="text-sm text-red-500">{error}</p> : null}
          </CardContent>
        </Card>

        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          {suggestions.map((suggestion) => (
            <Card key={suggestion.id} className="glass-card flex flex-col">
              <CardHeader>
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <Badge
                    variant={
                      suggestion.priority === "high" ||
                      suggestion.priority === "critical"
                        ? "destructive"
                        : "secondary"
                    }
                  >
                    {suggestion.priority.toUpperCase()}
                  </Badge>
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <Badge variant="outline">
                      {suggestion.suggestion_type}
                    </Badge>
                    <Badge variant="outline">#{suggestion.id}</Badge>
                    <span>
                      {new Date(suggestion.created_at).toLocaleDateString()}
                    </span>
                  </div>
                </div>
                <CardTitle className="mt-2 text-xl">
                  {suggestion.suggestion_type === "new_content" ? (
                    <FileText className="mr-2 inline h-5 w-5 text-brand" />
                  ) : null}
                  {suggestion.suggestion_type === "faq" ? (
                    <HelpCircle className="mr-2 inline h-5 w-5 text-amber-500" />
                  ) : null}
                  {suggestion.content_outline?.title ||
                    suggestion.content_outline?.question ||
                    suggestion.topic}
                </CardTitle>
                <CardDescription>Topic: {suggestion.topic}</CardDescription>
                {suggestion.page_url ? (
                  <p className="mt-2 break-all text-xs text-muted-foreground">
                    Page: {suggestion.page_url}
                  </p>
                ) : null}
              </CardHeader>
              <CardContent className="flex-grow space-y-3">
                {suggestion.suggestion_type === "new_content" &&
                suggestion.content_outline?.sections ? (
                  <div className="space-y-2">
                    <p className="text-sm font-semibold">Suggested Outline:</p>
                    <ul className="list-inside list-disc text-sm text-muted-foreground">
                      {suggestion.content_outline.sections.map(
                        (section: string) => (
                          <li key={section}>{section}</li>
                        ),
                      )}
                    </ul>
                  </div>
                ) : null}
                {suggestion.suggestion_type === "faq" &&
                suggestion.content_outline?.answer ? (
                  <div className="space-y-2">
                    <p className="text-sm font-semibold">Suggested Answer:</p>
                    <p className="rounded-md border border-border bg-muted/50 p-3 text-sm text-muted-foreground">
                      {suggestion.content_outline.answer}
                    </p>
                  </div>
                ) : null}
                {!["new_content", "faq"].includes(suggestion.suggestion_type) &&
                suggestion.content_outline ? (
                  <div className="whitespace-pre-wrap rounded-md border border-border bg-muted/50 p-3 font-mono text-sm text-muted-foreground">
                    {JSON.stringify(suggestion.content_outline, null, 2)}
                  </div>
                ) : null}
              </CardContent>
            </Card>
          ))}
          {suggestions.length === 0 && !loading ? (
            <Card className="glass-card p-10 text-center md:col-span-2">
              <Sparkles className="mx-auto mb-4 h-10 w-10 text-muted-foreground/60" />
              <h2 className="mb-2 text-lg font-semibold text-foreground">
                No AI suggestions yet
              </h2>
              <p className="text-muted-foreground">
                Generate a strategy to see content opportunities and outlines.
              </p>
            </Card>
          ) : null}
        </div>
      </main>
    </div>
  );
}
