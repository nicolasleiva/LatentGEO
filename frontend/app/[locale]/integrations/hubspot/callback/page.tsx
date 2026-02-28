"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Loader2 } from "lucide-react";
import { API_URL } from "@/lib/api";
import { fetchWithBackendAuth } from "@/lib/backend-auth";
import { withLocale } from "@/lib/locale-routing";

export default function HubSpotCallback() {
  const pathname = usePathname();
  const [status, setStatus] = useState("Processing...");
  const [error, setError] = useState("");

  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const code = params.get("code");
    const state = params.get("state");

    const exchangeCode = async (authCode: string) => {
      try {
        const response = await fetchWithBackendAuth(
          `${API_URL}/api/v1/hubspot/callback`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ code: authCode, state }),
          },
        );

        if (!response.ok) {
          throw new Error("Failed to exchange code");
        }

        const data = await response.json();
        setStatus("Connected successfully! Redirecting...");

        setTimeout(() => {
          window.location.assign(
            withLocale(pathname, "/integrations/hubspot/pages"),
          );
        }, 1500);
      } catch (err) {
        console.error(err);
        setError("Failed to connect to HubSpot. Please try again.");
      }
    };

    if (!state) {
      setError("Missing OAuth state");
    } else if (code) {
      exchangeCode(code);
    } else {
      setError("No authorization code found");
    }
  }, [pathname]);

  return (
    <div className="container mx-auto py-20 flex justify-center">
      <Card className="w-full max-w-md text-center">
        <CardHeader>
          <CardTitle>Connecting to HubSpot</CardTitle>
        </CardHeader>
        <CardContent>
          {error ? (
            <div className="text-red-500 mb-4">{error}</div>
          ) : (
            <div className="flex flex-col items-center gap-4">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
              <p className="text-muted-foreground">{status}</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

