"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { ArrowRight, Search } from "lucide-react";

import { createAudit } from "@/lib/api-client";
import { withLocale } from "@/lib/locale-routing";

function normalizeAuditUrl(input: string): string {
  const raw = input.trim();
  if (!raw) return "";
  if (/^[a-z][a-z0-9+.-]*:\/\//i.test(raw)) return raw;
  return `https://${raw}`;
}

function isLikelyPublicHost(hostname: string): boolean {
  if (!hostname) return false;
  if (hostname === "localhost") return true;
  if (/^\d{1,3}(?:\.\d{1,3}){3}$/.test(hostname)) return true;
  return hostname.includes(".");
}

type HomeAuditFormProps = {
  locale: string;
};

export default function HomeAuditForm({ locale }: HomeAuditFormProps) {
  const router = useRouter();
  const pathname = usePathname();
  const [url, setUrl] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const pendingUrl = sessionStorage.getItem("pendingAuditUrl");
    if (pendingUrl) {
      sessionStorage.removeItem("pendingAuditUrl");
      setUrl(pendingUrl);
    }
  }, []);

  const handleAudit = async (event?: React.FormEvent) => {
    event?.preventDefault();
    event?.stopPropagation();

    setError(null);

    if (!url.trim()) {
      setError("Please enter a valid URL");
      return;
    }

    const normalizedUrl = normalizeAuditUrl(url);
    let parsedUrl: URL;
    try {
      parsedUrl = new URL(normalizedUrl);
      if (!isLikelyPublicHost(parsedUrl.hostname)) {
        throw new Error("Invalid host");
      }
    } catch {
      setError("Please enter a valid domain or URL (e.g., ceibo.digital)");
      return;
    }

    setSubmitting(true);
    try {
      const newAudit = await createAudit({ url: normalizedUrl });
      router.push(
        withLocale(pathname || `/${locale}`, `/audits/${newAudit.id}`),
      );
    } catch (requestError: any) {
      const errorMessage =
        requestError?.message || "Please verify the server is running.";
      setError(`Connection error: ${errorMessage}`);
      setSubmitting(false);
    }
  };

  return (
    <form
      onSubmit={handleAudit}
      className="relative max-w-2xl"
      id="start-audit"
    >
      <div className="relative flex flex-col gap-2">
        <div className="relative flex items-center rounded-2xl border border-border p-2 shadow-2xl glass-panel">
          <Search className="ml-4 h-5 w-5 text-muted-foreground" />
          <input
            type="text"
            aria-label="Public page URL to audit"
            placeholder="Paste a public page URL (e.g., ceibo.digital)"
            className="flex-1 border-none bg-transparent px-4 py-4 text-base text-foreground outline-none placeholder:text-muted-foreground focus:ring-0"
            value={url}
            inputMode="url"
            autoComplete="url"
            onChange={(inputEvent) => {
              setUrl(inputEvent.target.value);
              setError(null);
            }}
            onKeyDown={(keyboardEvent) => {
              if (keyboardEvent.key === "Enter" && !submitting) {
                keyboardEvent.preventDefault();
                void handleAudit();
              }
            }}
            required
            disabled={submitting}
          />
          <button
            type="submit"
            disabled={submitting || !url.trim()}
            className="glass-button-primary flex items-center gap-2 rounded-xl px-6 py-3 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {submitting ? (
              <>
                <div className="h-5 w-5 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                Building your report
              </>
            ) : (
              <>
                Run free audit <ArrowRight className="h-5 w-5" />
              </>
            )}
          </button>
        </div>
        {error ? (
          <div
            role="alert"
            className="rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-2 text-sm text-red-600"
          >
            {error}
          </div>
        ) : null}
      </div>
    </form>
  );
}
