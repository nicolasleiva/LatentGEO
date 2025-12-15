# GEO Tools Auto-Generation Flow Diagram

## Complete Audit Pipeline with GEO Tools

```
┌─────────────────────────────────────────────────────────────────┐
│                    USER CREATES AUDIT                           │
│                    (via API or UI)                              │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              CELERY TASK: run_audit_task                        │
│              Status: RUNNING                                     │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│         STEP 1: MAIN AUDIT PIPELINE                             │
│         ├─ Crawl Site (discover pages)                          │
│         ├─ Audit Each Page (structure, content, E-E-A-T)        │
│         ├─ Analyze Competitors (if configured)                  │
│         └─ Generate Base Report                                 │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│         STEP 2: PAGESPEED ANALYSIS                              │
│         ├─ Collect Mobile Data                                  │
│         ├─ Collect Desktop Data                                 │
│         ├─ Calculate Core Web Vitals                            │
│         └─ Generate Performance Report                          │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│         STEP 3: AUTO-RUN GEO TOOLS ⭐ NEW!                      │
│                                                                  │
│         ┌──────────────────────────────────────────┐            │
│         │  3.1 KEYWORDS SERVICE                    │            │
│         │  ├─ Extract domain & category            │            │
│         │  ├─ Generate 10 keywords                 │            │
│         │  ├─ Calculate metrics:                   │            │
│         │  │  • Search Volume                      │            │
│         │  │  • Difficulty (0-100)                 │            │
│         │  │  • CPC                                │            │
│         │  │  • Intent                             │            │
│         │  │  • Current Rank                       │            │
│         │  │  • Opportunity Score                  │            │
│         │  └─ Sort by opportunity                  │            │
│         └──────────────────────────────────────────┘            │
│                          │                                       │
│                          ▼                                       │
│         ┌──────────────────────────────────────────┐            │
│         │  3.2 BACKLINKS SERVICE                   │            │
│         │  ├─ Generate 20 backlinks                │            │
│         │  ├─ Mix authority levels:                │            │
│         │  │  • High (DA 80+): 5 links             │            │
│         │  │  • Medium (DA 60-80): 5 links         │            │
│         │  │  • Low (DA <60): 10 links             │            │
│         │  ├─ Calculate metrics:                   │            │
│         │  │  • Domain Authority                   │            │
│         │  │  • Page Authority                     │            │
│         │  │  • Spam Score                         │            │
│         │  │  • Dofollow/Nofollow                  │            │
│         │  └─ Generate summary stats               │            │
│         └──────────────────────────────────────────┘            │
│                          │                                       │
│                          ▼                                       │
│         ┌──────────────────────────────────────────┐            │
│         │  3.3 RANK TRACKING SERVICE               │            │
│         │  ├─ Use keywords from 3.1                │            │
│         │  ├─ Generate positions (1-100)           │            │
│         │  ├─ Calculate changes:                   │            │
│         │  │  • Previous position                  │            │
│         │  │  • Change (+/-)                       │            │
│         │  └─ Calculate distribution:              │            │
│         │     • Top 3                              │            │
│         │     • Top 10                             │            │
│         │     • Top 20                             │            │
│         │     • Beyond 20                          │            │
│         └──────────────────────────────────────────┘            │
│                                                                  │
│         ⏱️  Total Time: ~0.3 seconds                            │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│         STEP 4: STORE RESULTS                                   │
│         ├─ Save to result dictionary                            │
│         ├─ Update database:                                     │
│         │  • audit.target_audit                                 │
│         │  • audit.pagespeed_data                               │
│         │  • audit.keywords_data ⭐                             │
│         │  • audit.backlinks_data ⭐                            │
│         │  • audit.rankings_data ⭐                             │
│         │  • audit.report_markdown                              │
│         │  • audit.fix_plan                                     │
│         └─ Status: COMPLETED                                    │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│         STEP 5: PDF GENERATION (Manual or Auto)                 │
│         ├─ Load complete data from DB                           │
│         ├─ Generate sections:                                   │
│         │  • Executive Summary                                  │
│         │  • Technical Audit                                    │
│         │  • PageSpeed Analysis                                 │
│         │  • Keywords Analysis ⭐ (with data!)                  │
│         │  • Backlinks Profile ⭐ (with data!)                  │
│         │  • Rankings Distribution ⭐ (with data!)              │
│         │  • Recommendations                                    │
│         └─ Save PDF to reports/audit_{id}/                      │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    AUDIT COMPLETE ✅                            │
│                                                                  │
│         Dashboard shows:                                         │
│         ✅ Technical audit results                              │
│         ✅ PageSpeed metrics                                    │
│         ✅ Keywords (10 with metrics)                           │
│         ✅ Backlinks (20 with DA/PA)                            │
│         ✅ Rankings (10 with positions)                         │
│         ✅ PDF ready for download                               │
└─────────────────────────────────────────────────────────────────┘
```

## Error Handling Flow

```
┌─────────────────────────────────────────────────────────────────┐
│         GEO TOOLS GENERATION                                    │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
                    ┌────────────────┐
                    │  Try Generate  │
                    └────────┬───────┘
                             │
                    ┌────────┴────────┐
                    │                 │
                    ▼                 ▼
            ┌──────────────┐   ┌──────────────┐
            │   SUCCESS    │   │    ERROR     │
            └──────┬───────┘   └──────┬───────┘
                   │                  │
                   │                  ▼
                   │          ┌──────────────┐
                   │          │  Log Error   │
                   │          └──────┬───────┘
                   │                 │
                   │                 ▼
                   │          ┌──────────────┐
                   │          │ Set Empty {} │
                   │          └──────┬───────┘
                   │                 │
                   └────────┬────────┘
                            │
                            ▼
                   ┌──────────────┐
                   │   CONTINUE   │
                   │  (No Crash)  │
                   └──────────────┘
```

## Data Flow

```
┌──────────────┐
│ Target Audit │ ──────┐
└──────────────┘       │
                       ▼
              ┌─────────────────┐
              │ Keywords Service│
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  Keywords List  │ ──────┐
              └─────────────────┘       │
                                        ▼
┌──────────────┐              ┌─────────────────┐
│ Target Audit │ ────────────▶│Backlinks Service│
└──────────────┘              └────────┬────────┘
                                       │
                                       ▼
                              ┌─────────────────┐
                              │ Backlinks Data  │
                              └─────────────────┘
                                       │
                                       ▼
              ┌─────────────────┐     │
              │  Keywords List  │ ────┤
              └─────────────────┘     │
                                      ▼
                             ┌─────────────────┐
                             │ Rankings Service│
                             └────────┬────────┘
                                      │
                                      ▼
                             ┌─────────────────┐
                             │  Rankings Data  │
                             └────────┬────────┘
                                      │
                                      ▼
                             ┌─────────────────┐
                             │  Result Dict    │
                             │  ├─ keywords    │
                             │  ├─ backlinks   │
                             │  └─ rankings    │
                             └────────┬────────┘
                                      │
                                      ▼
                             ┌─────────────────┐
                             │    Database     │
                             └────────┬────────┘
                                      │
                                      ▼
                             ┌─────────────────┐
                             │   PDF Report    │
                             └─────────────────┘
```

## Timing Breakdown

```
Total Audit Time: ~30-60 seconds
├─ Site Crawling: 10-20s
├─ Page Analysis: 10-20s
├─ PageSpeed API: 5-10s
├─ GEO Tools: 0.3s ⭐ (negligible!)
│  ├─ Keywords: 0.1s
│  ├─ Backlinks: 0.1s
│  └─ Rankings: 0.1s
├─ Report Generation: 5-10s
└─ Database Save: 1-2s
```

## Key Benefits

1. **Automatic** - No manual intervention needed
2. **Fast** - Only 0.3s overhead
3. **Complete** - All data ready before PDF
4. **Resilient** - Continues even if generation fails
5. **Consistent** - Same data in dashboard and PDF

---

**Legend:**
- ⭐ = New feature
- ✅ = Complete
- ⏱️ = Performance metric
