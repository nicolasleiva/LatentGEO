"use client";

import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import Link from "next/link";

export function GEOSkeleton({ auditId = "" }: { auditId?: string }) {
  return (
    <div className="min-h-screen bg-background text-foreground pb-20 animate-in fade-in duration-300">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header Skeleton */}
        <div className="mb-12">
          <Link href={`/audits/${auditId}`}>
            <Button
              variant="ghost"
              className="text-muted-foreground hover:text-foreground hover:bg-muted/40 mb-6 pl-0"
            >
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back to Audit
            </Button>
          </Link>

          <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
            <div className="space-y-3">
              <div className="h-12 w-64 bg-muted/50 rounded-lg animate-pulse" />
              <div className="h-6 w-96 bg-muted/30 rounded-lg animate-pulse" />
            </div>
            <div className="h-14 w-40 bg-muted/50 rounded-lg animate-pulse" />
          </div>
        </div>

        {/* Key Metrics Grid Skeleton */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-12">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="glass-card p-6 relative overflow-hidden">
              <div className="absolute top-0 right-0 p-4 opacity-5">
                <div className="w-24 h-24 bg-muted/40 rounded-full animate-pulse" />
              </div>
              <div className="h-4 w-24 bg-muted/40 rounded mb-2 animate-pulse" />
              <div className="h-10 w-20 bg-muted/60 rounded mb-1 animate-pulse" />
              <div className="h-3 w-32 bg-muted/30 rounded animate-pulse" />
            </div>
          ))}
        </div>

        {/* Opportunities Section Skeleton */}
        <div className="glass-card p-8 mb-8">
          <div className="h-8 w-48 bg-muted/50 rounded mb-6 animate-pulse" />
          <div className="h-4 w-96 bg-muted/30 rounded mb-8 animate-pulse" />

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="bg-muted/30 rounded-lg p-6 border border-border"
              >
                <div className="flex justify-between items-start mb-4">
                  <div className="h-6 w-32 bg-muted/50 rounded animate-pulse" />
                  <div className="h-6 w-16 bg-muted/50 rounded animate-pulse" />
                </div>
                <div className="h-4 w-full bg-muted/30 rounded mb-2 animate-pulse" />
                <div className="h-4 w-3/4 bg-muted/30 rounded animate-pulse" />
              </div>
            ))}
          </div>
        </div>

        {/* Competitor Benchmark Skeleton */}
        <div className="glass-card p-8 mb-8">
          <div className="h-8 w-48 bg-muted/50 rounded mb-6 animate-pulse" />
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {[1, 2, 3].map((i) => (
              <div key={i} className="bg-muted/30 rounded-lg p-6 text-center">
                <div className="h-4 w-24 bg-muted/50 rounded mx-auto mb-2 animate-pulse" />
                <div className="h-10 w-16 bg-muted/60 rounded mx-auto animate-pulse" />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function Loading() {
  return <GEOSkeleton />;
}
