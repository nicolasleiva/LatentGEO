"use client";

// Skeleton específico para RecentCitationsTable
export function CitationsTableSkeleton() {
  return (
    <div className="space-y-4 animate-pulse">
      {[1, 2, 3].map((i) => (
        <div
          key={i}
          className="bg-muted/30 border border-border rounded-xl p-4"
        >
          <div className="flex justify-between items-start mb-2">
            <div className="h-4 bg-muted/50 rounded w-1/3"></div>
            <div className="h-3 bg-muted/40 rounded w-16"></div>
          </div>
          <div className="h-3 bg-muted/40 rounded w-full mb-3"></div>
          <div className="flex items-center gap-4">
            <div className="h-3 bg-muted/40 rounded w-20"></div>
            <div className="h-3 bg-muted/40 rounded w-24"></div>
            <div className="h-3 bg-muted/40 rounded w-20"></div>
          </div>
        </div>
      ))}
    </div>
  );
}

// Skeleton para CitationHistory
export function HistorySkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      {[1, 2, 3].map((i) => (
        <div
          key={i}
          className="bg-muted/30 border border-border rounded-xl p-6"
        >
          <div className="flex justify-between items-start mb-4">
            <div>
              <div className="h-5 bg-muted/50 rounded w-32 mb-2"></div>
              <div className="h-3 bg-muted/40 rounded w-40"></div>
            </div>
            <div className="h-6 bg-muted/50 rounded w-16"></div>
          </div>
          <div className="flex items-center gap-2 mb-4">
            <div className="h-3 bg-muted/40 rounded w-20"></div>
            <div className="h-4 bg-muted/50 rounded w-8"></div>
          </div>
          <div className="flex flex-wrap gap-2">
            {[1, 2, 3].map((j) => (
              <div key={j} className="h-6 bg-muted/40 rounded w-24"></div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

// Skeleton para QueryDiscovery
export function QueryDiscoverySkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="flex gap-4">
        <div className="flex-1 h-10 bg-muted/40 rounded-lg"></div>
        <div className="h-10 w-32 bg-muted/50 rounded-lg"></div>
      </div>
      <div className="space-y-4">
        {[1, 2].map((i) => (
          <div
            key={i}
            className="bg-muted/30 border border-border rounded-xl p-6"
          >
            <div className="flex justify-between items-start mb-3">
              <div className="h-5 bg-muted/50 rounded w-1/2"></div>
              <div className="flex gap-2">
                <div className="h-6 bg-muted/40 rounded w-20"></div>
                <div className="h-6 bg-muted/40 rounded w-24"></div>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4 mb-4">
              <div className="h-3 bg-muted/40 rounded"></div>
              <div className="h-3 bg-muted/40 rounded"></div>
            </div>
            <div className="h-16 bg-green-500/10 rounded-lg"></div>
          </div>
        ))}
      </div>
    </div>
  );
}

// Skeleton para CompetitorAnalysis
export function CompetitorAnalysisSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="bg-muted/30 border border-border rounded-xl p-6">
        <div className="h-5 bg-muted/50 rounded w-48 mb-4"></div>
        <div className="space-y-3 mb-4">
          {[1, 2].map((i) => (
            <div key={i} className="flex gap-2">
              <div className="flex-1 h-10 bg-muted/40 rounded"></div>
              <div className="h-10 w-20 bg-muted/30 rounded"></div>
            </div>
          ))}
        </div>
        <div className="flex gap-4">
          <div className="h-10 w-32 bg-muted/40 rounded"></div>
          <div className="h-10 w-40 bg-muted/50 rounded"></div>
        </div>
      </div>
    </div>
  );
}

// Skeleton para SchemaGenerator y SchemaMultipleGenerator
export function SchemaGeneratorSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="bg-muted/30 border border-border rounded-xl p-6">
        <div className="space-y-4">
          <div className="h-4 bg-muted/50 rounded w-32 mb-2"></div>
          <div className="h-10 bg-muted/40 rounded"></div>
          <div className="h-4 bg-muted/50 rounded w-40 mb-2"></div>
          <div className="h-10 bg-muted/40 rounded"></div>
          <div className="h-12 bg-muted/50 rounded w-full"></div>
        </div>
      </div>
    </div>
  );
}

// Skeleton para ContentTemplates
export function ContentTemplatesSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="bg-muted/30 border border-border rounded-xl p-6">
        <div className="h-4 bg-muted/50 rounded w-24 mb-4"></div>
        <div className="h-10 bg-muted/40 rounded mb-4"></div>
        <div className="h-12 bg-muted/50 rounded w-full"></div>
      </div>
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="bg-muted/30 border border-border rounded-xl p-4"
          >
            <div className="flex justify-between items-start">
              <div className="w-full">
                <div className="h-5 bg-muted/50 rounded w-1/3 mb-2"></div>
                <div className="h-3 bg-muted/40 rounded w-1/2"></div>
              </div>
              <div className="h-6 bg-muted/40 rounded w-20"></div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// Skeleton para ContentAnalyze
export function ContentAnalyzeSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="bg-muted/30 border border-border rounded-xl p-6">
        <div className="h-4 bg-muted/50 rounded w-40 mb-4"></div>
        <div className="h-[200px] bg-muted/40 rounded mb-4"></div>
        <div className="h-12 bg-muted/50 rounded w-full"></div>
      </div>
      <div className="grid grid-cols-3 gap-6">
        <div className="bg-green-500/10 rounded-xl p-6 h-32"></div>
        <div className="bg-red-500/10 rounded-xl p-6 h-32"></div>
        <div className="bg-blue-500/10 rounded-xl p-6 h-32"></div>
      </div>
    </div>
  );
}

// Skeleton genérico para fallback
export function GenericSkeleton() {
  return (
    <div className="space-y-4 animate-pulse">
      <div className="h-4 bg-muted/50 rounded w-1/3"></div>
      <div className="h-32 bg-muted/30 border border-border rounded-xl"></div>
      <div className="h-4 bg-muted/50 rounded w-1/2"></div>
    </div>
  );
}
