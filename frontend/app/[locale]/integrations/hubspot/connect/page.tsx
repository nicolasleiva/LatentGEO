"use client";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useState } from "react";
import { API_URL } from "@/lib/api";
import { fetchWithBackendAuth } from "@/lib/backend-auth";

export default function HubSpotConnect() {
  const [loading, setLoading] = useState(false);

  const handleConnect = async () => {
    setLoading(true);
    try {
      const response = await fetchWithBackendAuth(
        `${API_URL}/api/v1/hubspot/auth-url`,
      );
      const data = await response.json();
      window.location.href = data.url;
    } catch (error) {
      console.error("Error getting auth url:", error);
      setLoading(false);
    }
  };

  return (
    <div className="container mx-auto py-20 flex justify-center">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Connect HubSpot</CardTitle>
          <CardDescription>
            Connect your HubSpot portal to audit and optimize your pages
            automatically.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-4">
            <div className="bg-orange-50 p-4 rounded-md border border-orange-100">
              <h3 className="font-medium text-orange-800 mb-2">
                Features enabled:
              </h3>
              <ul className="list-disc list-inside text-sm text-orange-700 space-y-1">
                <li>Sync CMS pages</li>
                <li>Audit content for SEO/GEO</li>
                <li>Apply fixes directly</li>
                <li>Track changes</li>
              </ul>
            </div>

            <Button
              onClick={handleConnect}
              className="w-full bg-[#ff7a59] hover:bg-[#ff7a59]/90"
              disabled={loading}
            >
              {loading ? "Connecting..." : "Connect HubSpot Portal"}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

