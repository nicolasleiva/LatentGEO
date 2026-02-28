"use client";

import { useState } from "react";
import { Copy, Check, Sparkles, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { fetchWithBackendAuth } from "@/lib/backend-auth";

interface SchemaResult {
  schema_type: string;
  schema_json: string;
  recommendations: string[];
}

interface SchemaGeneratorProps {
  backendUrl: string;
}

export default function SchemaGenerator({ backendUrl }: SchemaGeneratorProps) {
  const [form, setForm] = useState({ url: "", schemaType: "auto" });
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SchemaResult | null>(null);
  const [ui, setUi] = useState<{ error: string | null; copied: boolean }>({
    error: null,
    copied: false,
  });

  const generateSchema = async () => {
    if (!form.url.trim()) return;

    setLoading(true);
    setUi((prev) => ({ ...prev, error: null }));

    try {
      const res = await fetchWithBackendAuth(
        `${backendUrl}/api/v1/geo/schema-generator`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            url: form.url,
            schema_type: form.schemaType === "auto" ? null : form.schemaType,
          }),
        },
      );

      if (!res.ok) throw new Error("Failed to generate schema");
      const data = await res.json();
      setResult(data);
    } catch (err: any) {
      setUi((prev) => ({ ...prev, error: err.message }));
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = () => {
    if (result?.schema_json) {
      navigator.clipboard.writeText(result.schema_json);
      setUi((prev) => ({ ...prev, copied: true }));
      setTimeout(() => {
        setUi((prev) => ({ ...prev, copied: false }));
      }, 2000);
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-muted/30 border border-border rounded-xl p-6">
        <div className="space-y-4">
          <div>
            <Label className="text-muted-foreground">Page URL</Label>
            <Input
              placeholder="https://example.com/page"
              value={form.url}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, url: e.target.value }))
              }
              className="mt-2 bg-muted/30 border-border/70 text-foreground placeholder:text-muted-foreground"
            />
          </div>

          <div>
            <Label className="text-muted-foreground">
              Schema Type (Optional)
            </Label>
            <Select
              value={form.schemaType}
              onValueChange={(value) =>
                setForm((prev) => ({ ...prev, schemaType: value }))
              }
            >
              <SelectTrigger className="mt-2 bg-muted/30 border-border/70 text-foreground">
                <SelectValue placeholder="Auto-detect" />
              </SelectTrigger>
              <SelectContent className="bg-popover border-border/70">
                <SelectItem value="auto">Auto-detect</SelectItem>
                <SelectItem value="Organization">Organization</SelectItem>
                <SelectItem value="LocalBusiness">LocalBusiness</SelectItem>
                <SelectItem value="Product">Product</SelectItem>
                <SelectItem value="Service">Service</SelectItem>
                <SelectItem value="Article">Article</SelectItem>
                <SelectItem value="BlogPosting">BlogPosting</SelectItem>
                <SelectItem value="FAQPage">FAQPage</SelectItem>
                <SelectItem value="HowTo">HowTo</SelectItem>
                <SelectItem value="Event">Event</SelectItem>
                <SelectItem value="Course">Course</SelectItem>
                <SelectItem value="SoftwareApplication">
                  SoftwareApplication
                </SelectItem>
              </SelectContent>
            </Select>
          </div>

          <Button
            onClick={generateSchema}
            disabled={loading || !form.url.trim()}
            className="glass-button-primary w-full"
          >
            {loading ? (
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-foreground"></div>
            ) : (
              <>
                <Sparkles className="w-4 h-4 mr-2" />
                Generate Schema
              </>
            )}
          </Button>
        </div>
      </div>

      {ui.error && (
        <div className="flex items-center gap-2 text-red-400 py-4">
          <AlertCircle className="w-5 h-5" />
          <span>Error: {ui.error}</span>
        </div>
      )}

      {result && (
        <div className="bg-muted/30 border border-border rounded-xl p-6">
          <div className="flex justify-between items-center mb-4">
            <div>
              <h3 className="font-semibold text-foreground text-lg">
                Generated Schema: {result.schema_type}
              </h3>
              <p className="text-muted-foreground text-sm">
                Copy this JSON-LD to your page&apos;s &lt;head&gt;
              </p>
            </div>
            <Button
              variant="outline"
              onClick={copyToClipboard}
              className="border-border/70 text-foreground"
            >
              {ui.copied ? (
                <>
                  <Check className="w-4 h-4 mr-2" /> Copied!
                </>
              ) : (
                <>
                  <Copy className="w-4 h-4 mr-2" /> Copy
                </>
              )}
            </Button>
          </div>

          <Textarea
            value={result.schema_json}
            readOnly
            className="bg-muted/50 border-border text-green-400 font-mono text-sm min-h-[200px]"
          />

          {result.recommendations.length > 0 && (
            <div className="mt-6">
              <h4 className="font-semibold text-foreground mb-3">
                Recommendations
              </h4>
              <ul className="space-y-2">
                {result.recommendations.map((rec) => (
                  <li
                    key={rec}
                    className="text-muted-foreground text-sm flex items-start gap-2"
                  >
                    <span className="text-blue-400">•</span> {rec}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

