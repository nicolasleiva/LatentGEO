"use client";

import { useState } from "react";
import {
  Award,
  Copy,
  Check,
  Sparkles,
  AlertCircle,
  FileText,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { fetchWithBackendAuth } from "@/lib/backend-auth";

interface Template {
  id: string;
  name: string;
  description: string;
  category: string;
  structure: string;
  tips: string[];
}

interface ContentTemplatesProps {
  backendUrl: string;
}

export default function ContentTemplates({
  backendUrl,
}: ContentTemplatesProps) {
  const [category, setCategory] = useState("all");
  const [loading, setLoading] = useState(false);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<Template | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const categories = [
    { value: "all", label: "All Categories" },
    { value: "product", label: "Product Pages" },
    { value: "service", label: "Service Pages" },
    { value: "blog", label: "Blog/Articles" },
    { value: "landing", label: "Landing Pages" },
    { value: "about", label: "About Pages" },
    { value: "faq", label: "FAQ Pages" },
  ];

  const fetchTemplates = async () => {
    setLoading(true);
    setError(null);

    try {
      const res = await fetchWithBackendAuth(
        `${backendUrl}/api/geo/content-templates?category=${category}`,
      );
      if (!res.ok) throw new Error("Failed to fetch templates");
      const data = await res.json();
      setTemplates(data.templates || []);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const copyTemplate = () => {
    if (selectedTemplate) {
      navigator.clipboard.writeText(selectedTemplate.structure);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-muted/30 border border-border rounded-xl p-6">
        <div className="space-y-4">
          <div>
            <Label className="text-muted-foreground">Category</Label>
            <Select value={category} onValueChange={setCategory}>
              <SelectTrigger className="mt-2 bg-muted/30 border-border/70 text-foreground">
                <SelectValue placeholder="Select category" />
              </SelectTrigger>
              <SelectContent className="bg-popover border-border/70">
                {categories.map((cat) => (
                  <SelectItem key={cat.value} value={cat.value}>
                    {cat.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <Button
            onClick={fetchTemplates}
            disabled={loading}
            className="glass-button-primary w-full"
          >
            {loading ? (
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-foreground"></div>
            ) : (
              <>
                <FileText className="w-4 h-4 mr-2" />
                Load Templates
              </>
            )}
          </Button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 text-red-400 py-4">
          <AlertCircle className="w-5 h-5" />
          <span>Error: {error}</span>
        </div>
      )}

      {templates.length > 0 && !selectedTemplate && (
        <div className="space-y-3">
          <p className="text-muted-foreground mb-4">
            Select a template to view:
          </p>
          {templates.map((template) => (
            <button
              key={template.id}
              onClick={() => setSelectedTemplate(template)}
              className="w-full text-left bg-muted/30 border border-border rounded-xl p-4 hover:bg-muted/40 transition-colors"
            >
              <div className="flex justify-between items-start">
                <div>
                  <h4 className="font-semibold text-foreground">
                    {template.name}
                  </h4>
                  <p className="text-muted-foreground text-sm mt-1">
                    {template.description}
                  </p>
                </div>
                <span className="bg-muted/40 text-muted-foreground px-2 py-1 rounded text-xs capitalize">
                  {template.category}
                </span>
              </div>
            </button>
          ))}
        </div>
      )}

      {selectedTemplate && (
        <div className="bg-muted/30 border border-border rounded-xl p-6">
          <div className="flex justify-between items-start mb-4">
            <div>
              <h3 className="font-semibold text-foreground text-xl">
                {selectedTemplate.name}
              </h3>
              <p className="text-muted-foreground">
                {selectedTemplate.description}
              </p>
            </div>
            <div className="flex gap-2">
              <Button
                variant="outline"
                onClick={() => setSelectedTemplate(null)}
                className="border-border/70 text-foreground"
              >
                Back
              </Button>
              <Button
                variant="outline"
                onClick={copyTemplate}
                className="border-border/70 text-foreground"
              >
                {copied ? (
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
          </div>

          <Textarea
            value={selectedTemplate.structure}
            readOnly
            className="bg-muted/50 border-border text-foreground font-mono text-sm min-h-[300px] mb-6"
          />

          {selectedTemplate.tips.length > 0 && (
            <div>
              <h4 className="font-semibold text-foreground mb-3 flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-yellow-400" />
                GEO Optimization Tips
              </h4>
              <ul className="space-y-2">
                {selectedTemplate.tips.map((tip, idx) => (
                  <li
                    key={idx}
                    className="text-muted-foreground text-sm flex items-start gap-2"
                  >
                    <span className="text-yellow-400">•</span> {tip}
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
