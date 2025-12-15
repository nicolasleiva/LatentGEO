# PageSpeed Frontend Implementation Guide

## Overview

This document provides implementation guidance for the frontend components needed to display complete PageSpeed data and handle manual/automatic PageSpeed triggers.

## Backend Status: ✅ COMPLETE

All backend functionality is implemented and working:
- ✅ Auto-trigger PageSpeed during PDF generation
- ✅ Fast dashboard loading (no PageSpeed blocking)
- ✅ Manual PageSpeed trigger endpoint
- ✅ Complete data return (all opportunities, diagnostics, accessibility, SEO, best practices)
- ✅ Complete context loading for LLM (PageSpeed + keywords + backlinks + rankings + LLM visibility + AI content)
- ✅ GitHub App context parity

## Frontend Tasks Remaining

### Task 7: Create PageSpeed Results Component

**File**: `frontend/components/pagespeed-results.tsx`

**Purpose**: Display COMPLETE PageSpeed data with all sections

**Required Sections**:
1. Lighthouse Scores (Performance, Accessibility, Best Practices, SEO)
2. Core Web Vitals (LCP, FCP, CLS, TBT, Speed Index, FID/INP, TTFB)
3. Full Metrics
4. Opportunities (ALL opportunities with savings estimates)
5. Diagnostics (ALL diagnostics)
6. Accessibility Audits (ALL accessibility checks)
7. SEO Audits (ALL SEO checks)
8. Best Practices (ALL best practice checks)
9. Screenshots
10. Metadata (fetch time, user agent, Lighthouse version)

**Component Structure**:
```typescript
interface PageSpeedResultsProps {
  data: {
    mobile?: PageSpeedData;
    desktop?: PageSpeedData;
  };
}

export function PageSpeedResults({ data }: PageSpeedResultsProps) {
  const [activeTab, setActiveTab] = useState<'mobile' | 'desktop'>('mobile');
  const currentData = data[activeTab];

  if (!currentData) {
    return <div>No data available</div>;
  }

  return (
    <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as any)}>
      <TabsList>
        <TabsTrigger value="mobile">Mobile</TabsTrigger>
        <TabsTrigger value="desktop">Desktop</TabsTrigger>
      </TabsList>

      <TabsContent value={activeTab}>
        {/* Lighthouse Scores */}
        <ScoreSection
          performance={currentData.performance_score}
          accessibility={currentData.accessibility_score}
          bestPractices={currentData.best_practices_score}
          seo={currentData.seo_score}
        />

        {/* Core Web Vitals */}
        <CoreWebVitalsSection metrics={currentData.core_web_vitals} />

        {/* Full Metrics */}
        <MetricsSection metrics={currentData.metrics} />

        {/* Opportunities (ALL of them) */}
        <OpportunitiesSection opportunities={currentData.opportunities} />

        {/* Diagnostics (ALL of them) */}
        <DiagnosticsSection diagnostics={currentData.diagnostics} />

        {/* Accessibility Audits (ALL of them) */}
        <AccessibilitySection audits={currentData.accessibility} />

        {/* SEO Audits (ALL of them) */}
        <SEOSection audits={currentData.seo} />

        {/* Best Practices (ALL of them) */}
        <BestPracticesSection audits={currentData.best_practices} />

        {/* Screenshots */}
        <ScreenshotsSection screenshots={currentData.screenshots} />

        {/* Metadata */}
        <MetadataSection metadata={currentData.metadata} />
      </TabsContent>
    </Tabs>
  );
}
```

**Data Structure** (from backend):
```typescript
interface PageSpeedData {
  url: string;
  strategy: "mobile" | "desktop";
  performance_score: number;
  accessibility_score: number;
  best_practices_score: number;
  seo_score: number;
  core_web_vitals: {
    lcp: number;
    fid: number;
    cls: number;
    fcp: number;
    ttfb: number;
  };
  metadata: {
    fetch_time: string;
    user_agent: string;
    lighthouse_version: string;
    network_throttling: string;
    benchmark_index: number;
  };
  screenshots: Array<{
    data: string;
    timestamp: number;
  }>;
  metrics: {
    fcp: number;
    lcp: number;
    tbt: number;
    cls: number;
    si: number;
  };
  opportunities: {
    uses_long_cache_ttl: AuditData;
    uses_optimized_images: AuditData;
    uses_responsive_images: AuditData;
    modern_image_formats: AuditData;
    offscreen_images: AuditData;
    font_display: AuditData;
    render_blocking_resources: AuditData;
    server_response_time: AuditData;
    redirects: AuditData;
    uses_rel_preconnect: AuditData;
    uses_rel_preload: AuditData;
    critical_request_chains: AuditData;
    network_rtt: AuditData;
    network_server_latency: AuditData;
    lcp_lazy_loaded: AuditData;
    largest_contentful_paint_element: AuditData;
    layout_shift_elements: AuditData;
    duplicated_javascript: AuditData;
    legacy_javascript: AuditData;
    third_party_summary: AuditData;
    third_party_facades: AuditData;
  };
  diagnostics: {
    unused_javascript: AuditData;
    unused_css_rules: AuditData;
    unsized_images: AuditData;
    total_byte_weight: AuditData;
    long_tasks: AuditData;
    dom_size: AuditData;
    bootup_time: AuditData;
    mainthread_work_breakdown: AuditData;
    duplicated_javascript: AuditData;
    uses_passive_event_listeners: AuditData;
    no_document_write: AuditData;
    efficient_animated_content: AuditData;
    non_composited_animations: AuditData;
    viewport: AuditData;
    user_timings: AuditData;
    critical_request_chains: AuditData;
    font_size: AuditData;
    resource_summary: AuditData;
    network_requests: AuditData;
  };
  accessibility: {
    score: number;
    aria_allowed_attr: AuditData;
    aria_required_attr: AuditData;
    aria_valid_attr_value: AuditData;
    aria_valid_attr: AuditData;
    button_name: AuditData;
    bypass: AuditData;
    color_contrast: AuditData;
    document_title: AuditData;
    duplicate_id_active: AuditData;
    duplicate_id_aria: AuditData;
    form_field_multiple_labels: AuditData;
    frame_title: AuditData;
    heading_order: AuditData;
    html_has_lang: AuditData;
    html_lang_valid: AuditData;
    image_alt: AuditData;
    input_image_alt: AuditData;
    label: AuditData;
    link_name: AuditData;
    list: AuditData;
    listitem: AuditData;
    meta_refresh: AuditData;
    meta_viewport: AuditData;
    object_alt: AuditData;
    tabindex: AuditData;
    td_headers_attr: AuditData;
    th_has_data_cells: AuditData;
    valid_lang: AuditData;
    video_caption: AuditData;
  };
  seo: {
    score: number;
    viewport: AuditData;
    document_title: AuditData;
    meta_description: AuditData;
    http_status_code: AuditData;
    link_text: AuditData;
    crawlable_anchors: AuditData;
    is_crawlable: AuditData;
    robots_txt: AuditData;
    image_alt: AuditData;
    hreflang: AuditData;
    canonical: AuditData;
    font_size: AuditData;
    plugins: AuditData;
    tap_targets: AuditData;
  };
  best_practices: {
    score: number;
    errors_in_console: AuditData;
    image_aspect_ratio: AuditData;
    image_size_responsive: AuditData;
    js_libraries: AuditData;
    deprecations: AuditData;
    mainthread_work_breakdown: AuditData;
    bootup_time: AuditData;
    uses_http2: AuditData;
    uses_passive_event_listeners: AuditData;
    no_document_write: AuditData;
    geolocation_on_start: AuditData;
    doctype: AuditData;
    charset: AuditData;
  };
}

interface AuditData {
  score: number | null;
  displayValue: string;
  numericValue: number | null;
  title: string;
}
```

### Task 8: Update Audit Detail Page

**File**: `frontend/app/audits/[id]/page.tsx`

**Changes Needed**:

1. **Remove PageSpeed auto-trigger on page load**
2. **Add conditional rendering for PageSpeed section**
3. **Add "Run PageSpeed" button when data not available**
4. **Add "Refresh" button when data is stale**
5. **Display timestamp of last PageSpeed analysis**
6. **Add "Generate PDF" button that triggers PDF with auto-PageSpeed**

**Implementation**:

```typescript
export default function AuditDetailPage({ params }: { params: { id: string } }) {
  const [audit, setAudit] = useState<Audit | null>(null);
  const [pagespeedLoading, setPagespeedLoading] = useState(false);
  const [pdfGenerating, setPdfGenerating] = useState(false);

  // Load audit details (fast, no PageSpeed trigger)
  useEffect(() => {
    loadAuditDetails();
  }, [params.id]);

  const loadAuditDetails = async () => {
    const response = await fetch(`/api/audits/${params.id}`);
    const data = await response.json();
    setAudit(data);
  };

  // Manual PageSpeed trigger
  const runPageSpeed = async () => {
    setPagespeedLoading(true);
    try {
      const response = await fetch(`/api/audits/${params.id}/run-pagespeed`, {
        method: 'POST'
      });
      const result = await response.json();
      
      // Update audit with complete PageSpeed data
      setAudit(prev => ({
        ...prev,
        pagespeed_data: result.data,
        pagespeed_available: true,
        pagespeed_stale: false
      }));
      
      toast.success('PageSpeed analysis completed');
    } catch (error) {
      toast.error('PageSpeed analysis failed');
    } finally {
      setPagespeedLoading(false);
    }
  };

  // PDF generation with automatic PageSpeed
  const generatePDF = async () => {
    setPdfGenerating(true);
    try {
      const response = await fetch(`/api/audits/${params.id}/generate-pdf`, {
        method: 'POST'
      });
      const result = await response.json();
      
      toast.success('PDF generated successfully');
      // Download or display PDF
      window.open(`/api/audits/${params.id}/download-pdf`, '_blank');
    } catch (error) {
      toast.error('PDF generation failed');
    } finally {
      setPdfGenerating(false);
    }
  };

  return (
    <div>
      {/* Audit details load immediately */}
      <AuditHeader audit={audit} />
      
      {/* PageSpeed section with conditional rendering */}
      <Card>
        <CardHeader>
          <CardTitle>PageSpeed Analysis</CardTitle>
        </CardHeader>
        <CardContent>
          {!audit?.pagespeed_available && (
            <div className="text-center py-8">
              <p className="text-muted-foreground mb-4">
                PageSpeed analysis not yet run
              </p>
              <Button onClick={runPageSpeed} disabled={pagespeedLoading}>
                {pagespeedLoading ? 'Analyzing...' : 'Run PageSpeed Analysis'}
              </Button>
            </div>
          )}
          
          {audit?.pagespeed_available && (
            <>
              {audit.pagespeed_stale && (
                <Alert className="mb-4">
                  <AlertDescription>
                    PageSpeed data is more than 24 hours old.
                    <Button variant="link" onClick={runPageSpeed}>
                      Refresh
                    </Button>
                  </AlertDescription>
                </Alert>
              )}
              
              {/* Display COMPLETE PageSpeed data */}
              <PageSpeedResults data={audit.pagespeed_data} />
            </>
          )}
        </CardContent>
      </Card>
      
      {/* PDF generation button */}
      <Button onClick={generatePDF} disabled={pdfGenerating}>
        {pdfGenerating ? 'Generating PDF...' : 'Generate PDF Report'}
      </Button>
    </div>
  );
}
```

## API Endpoints Summary

### GET /api/audits/{id}
**Fast load, no PageSpeed trigger**
```json
{
  "id": 1,
  "url": "https://example.com",
  "status": "completed",
  "pagespeed_data": {...} | null,
  "pagespeed_available": true | false,
  "pagespeed_stale": true | false,
  ...
}
```

### POST /api/audits/{id}/run-pagespeed
**Manual trigger, returns complete data**
```json
{
  "success": true,
  "data": {
    "mobile": {
      "url": "...",
      "strategy": "mobile",
      "performance_score": 85,
      "accessibility_score": 92,
      "best_practices_score": 88,
      "seo_score": 95,
      "core_web_vitals": {...},
      "metadata": {...},
      "screenshots": [...],
      "metrics": {...},
      "opportunities": {...},  // 20+ audits
      "diagnostics": {...},    // 20+ audits
      "accessibility": {...},  // 30+ checks
      "seo": {...},           // 15+ checks
      "best_practices": {...} // 15+ checks
    },
    "desktop": {...}
  },
  "message": "PageSpeed analysis completed",
  "strategies_analyzed": ["mobile", "desktop"]
}
```

### POST /api/audits/{id}/generate-pdf
**Auto-trigger PageSpeed if needed, generate PDF**
```json
{
  "success": true,
  "pdf_path": "/reports/audit_1/Reporte_Consolidado_audit_1.pdf",
  "message": "PDF generated successfully with PageSpeed data",
  "pagespeed_included": true,
  "file_size": 1234567
}
```

## Testing the Implementation

### 1. Test Fast Dashboard Loading
```bash
# Should return immediately without triggering PageSpeed
curl http://localhost:8000/api/audits/1
```

### 2. Test Manual PageSpeed Trigger
```bash
# Should trigger PageSpeed and return complete data
curl -X POST http://localhost:8000/api/audits/1/run-pagespeed
```

### 3. Test PDF Generation with Auto-PageSpeed
```bash
# Should auto-trigger PageSpeed if not cached, then generate PDF
curl -X POST http://localhost:8000/api/audits/1/generate-pdf
```

### 4. Test PageSpeed Staleness
```bash
# Force refresh even if cached
curl -X POST "http://localhost:8000/api/audits/1/generate-pdf?force_pagespeed_refresh=true"
```

## Implementation Priority

1. ✅ **Backend (COMPLETE)** - All functionality working
2. 🔄 **Frontend Basic** - Add "Run PageSpeed" button and conditional rendering
3. 🔄 **Frontend Complete** - Full PageSpeedResults component with all sections

## Next Steps

1. Update `frontend/app/audits/[id]/page.tsx` with conditional PageSpeed rendering
2. Create basic `PageSpeedResults` component showing scores and key metrics
3. Gradually expand `PageSpeedResults` to show all sections (opportunities, diagnostics, etc.)
4. Test end-to-end flow: Dashboard load → Manual PageSpeed → PDF generation

## Notes

- Backend is fully functional and ready to use
- Frontend changes are optional enhancements for better UX
- PDF generation will work correctly even without frontend changes
- The key fix (auto-PageSpeed during PDF generation) is already implemented
