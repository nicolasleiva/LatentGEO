"use client";

import { useState, startTransition } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Network } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api-client";

type BacklinksAnalyzeFormProps = {
  auditId: string;
  initialDomain: string;
};

export default function BacklinksAnalyzeForm({
  auditId,
  initialDomain,
}: BacklinksAnalyzeFormProps) {
  const router = useRouter();
  const [domain, setDomain] = useState(initialDomain);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleAnalyze() {
    if (!domain) return;

    setLoading(true);
    setError("");

    try {
      await api.analyzeBacklinks(auditId, domain);
      startTransition(() => {
        router.refresh();
      });
    } catch {
      setError("Failed to analyze links.");
      setLoading(false);
      return;
    }

    setLoading(false);
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-4 md:flex-row">
        <Input
          className="glass-input max-w-md"
          placeholder="example.com"
          value={domain}
          onChange={(event) => setDomain(event.target.value)}
        />
        <Button
          onClick={handleAnalyze}
          disabled={loading}
          className="glass-button-primary"
        >
          {loading ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Analyzing...
            </>
          ) : (
            <>
              <Network className="mr-2 h-4 w-4" />
              Analyze All
            </>
          )}
        </Button>
      </div>
      {error ? <p className="text-sm text-red-500">{error}</p> : null}
    </div>
  );
}
