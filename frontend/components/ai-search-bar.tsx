"use client";

import { useState } from "react";
import { Search, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface AISearchBarProps {
  onSearch: (query: string) => void;
  placeholder?: string;
}

export function AISearchBar({
  onSearch,
  placeholder = "Ask AI about your site or enter a URL to audit...",
}: AISearchBarProps) {
  const [query, setQuery] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      onSearch(query);
      setQuery("");
    }
  };

  return (
    <form onSubmit={handleSubmit} className="relative w-full max-w-3xl">
      <div className="relative flex items-center gap-2">
        <div className="absolute left-4 top-1/2 -translate-y-1/2 text-muted-foreground">
          <Sparkles className="h-5 w-5" />
        </div>
        <Input
          type="text"
          placeholder={placeholder}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="h-14 pl-12 pr-32 text-base bg-background border border-border shadow-sm focus-visible:ring-1 focus-visible:ring-ring"
        />
        <Button
          type="submit"
          size="lg"
          className="absolute right-2 top-1/2 -translate-y-1/2"
        >
          <Search className="h-4 w-4 mr-2" />
          Search
        </Button>
      </div>
    </form>
  );
}
