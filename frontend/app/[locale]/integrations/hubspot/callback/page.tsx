"use client";

import { useEffect, useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Loader2 } from "lucide-react";
import { API_URL } from "@/lib/api";
import { fetchWithBackendAuth } from "@/lib/backend-auth";

function CallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const code = searchParams.get("code");
  const [status, setStatus] = useState("Processing...");
  const [error, setError] = useState("");

  useEffect(() => {
    const exchangeCode = async (authCode: string) => {
      try {
        const response = await fetchWithBackendAuth(
          `${API_URL}/api/hubspot/callback`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ code: authCode }),
          },
        );

        if (!response.ok) {
          throw new Error("Failed to exchange code");
        }

        const data = await response.json();
        setStatus("Connected successfully! Redirecting...");

        // Redirect to pages list
        setTimeout(() => {
          router.push("/integrations/hubspot/pages");
        }, 1500);
      } catch (err) {
        console.error(err);
        setError("Failed to connect to HubSpot. Please try again.");
      }
    };

    if (code) {
      exchangeCode(code);
    } else {
      setError("No authorization code found");
    }
  }, [code, router]);

  return (
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
  );
}

export default function HubSpotCallback() {
  return (
    <div className="container mx-auto py-20 flex justify-center">
      <Suspense
        fallback={
          <Card className="w-full max-w-md text-center">
            <CardContent className="pt-6">
              <Loader2 className="h-8 w-8 animate-spin text-primary mx-auto" />
              <p className="mt-2 text-muted-foreground">Loading...</p>
            </CardContent>
          </Card>
        }
      >
        <CallbackContent />
      </Suspense>
    </div>
  );
}
