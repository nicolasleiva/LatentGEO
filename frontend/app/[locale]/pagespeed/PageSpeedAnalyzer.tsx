"use client";

import { useState, startTransition } from "react";
import { Loader2 } from "lucide-react";

import { api } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CoreWebVitalsChart } from "@/components/core-web-vitals-chart";

export default function PageSpeedAnalyzer() {
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<any>(null);

  const analyze = async () => {
    if (!url) return;
    setLoading(true);
    try {
      const result = await api.comparePageSpeed(url);
      startTransition(() => {
        setData(result);
      });
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Card className="glass-card">
        <CardHeader>
          <CardTitle>Analyze a URL</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3 md:flex-row">
          <Input
            className="glass-input"
            placeholder="https://example.com"
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            onKeyDown={(event) => event.key === "Enter" && analyze()}
          />
          <Button
            onClick={analyze}
            disabled={loading}
            className="glass-button-primary"
          >
            {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
            {loading ? "Analyzing..." : "Analyze"}
          </Button>
        </CardContent>
      </Card>

      {data ? <CoreWebVitalsChart data={data} /> : null}
    </>
  );
}
