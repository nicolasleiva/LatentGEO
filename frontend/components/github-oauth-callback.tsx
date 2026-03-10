"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Loader2, CheckCircle2, XCircle } from "lucide-react";
import { API_URL } from "@/lib/api";
import { fetchWithBackendAuth } from "@/lib/backend-auth";
import { withLocale } from "@/lib/locale-routing";

type GitHubOAuthCallbackProps = {
  fallbackHref?: string;
  onRedirect?: (href: string) => void;
};

export default function GitHubOAuthCallback({
  fallbackHref = "/audits",
  onRedirect,
}: GitHubOAuthCallbackProps) {
  const pathname = usePathname();
  const [status, setStatus] = useState<"loading" | "success" | "error">(
    "loading",
  );
  const [message, setMessage] = useState("Conectando con GitHub...");
  const [debugCode, setDebugCode] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;

    const params = new URLSearchParams(window.location.search);
    const code = params.get("code");
    const state = params.get("state");
    const error = params.get("error");
    setDebugCode(code);

    if (error) {
      setStatus("error");
      setMessage("GitHub authorization error");
      return;
    }

    if (!code) {
      setStatus("error");
      setMessage("Authorization code not received");
      return;
    }

    if (!state) {
      setStatus("error");
      setMessage("OAuth state not received");
      return;
    }

    const exchangeCode = async () => {
      try {
        const response = await fetchWithBackendAuth(
          `${API_URL}/api/v1/github/callback`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({ code, state }),
          },
        );

        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(data?.detail || "Error exchanging authorization code");
        }

        const nextHref =
          typeof data?.return_to === "string" && data.return_to
            ? withLocale(pathname, data.return_to)
            : withLocale(pathname, fallbackHref);

        setStatus("success");
        setMessage("Connection successful! Redirecting...");

        setTimeout(() => {
          if (onRedirect) {
            onRedirect(nextHref);
            return;
          }
          window.location.href = nextHref;
        }, 1200);
      } catch (err) {
        console.error(err);
        setStatus("error");
        setMessage("Error al conectar con el servidor");
      }
    };

    void exchangeCode();
  }, [fallbackHref, onRedirect, pathname]);

  return (
    <div className="flex h-screen w-full items-center justify-center bg-gray-50">
      <Card className="w-[400px]">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            {status === "loading" && (
              <Loader2 className="h-6 w-6 animate-spin" />
            )}
            {status === "success" && (
              <CheckCircle2 className="h-6 w-6 text-green-500" />
            )}
            {status === "error" && <XCircle className="h-6 w-6 text-red-500" />}
            GitHub connection
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="mb-4 text-muted-foreground">{message}</p>
          {status === "error" && (
            <div className="break-all rounded bg-red-50 p-2 text-xs text-red-800">
              <p>If the error persists, copy this code and send it to support:</p>
              <code className="mt-2 block font-mono font-bold">{debugCode}</code>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
