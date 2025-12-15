# PDF Generation Data Integration Fix

## Problem Description

The PDF generation is working but producing reports with incomplete or missing data. Specifically:

1. **PageSpeed data exists** in `reports/audit_65/pagespeed.json` but shows as "Datos no disponibles" in the PDF
2. **Other GEO tools data** (keywords, backlinks, rankings) are being generated but not properly integrated into the report
3. **Report quality is poor** with generic content instead of data-driven insights

## Root Cause Analysis

### Issue 1: Data Flow Verification Needed
- PageSpeed data is being collected and stored correctly
- The data is being passed to `PipelineService.generate_report()` 
- Need to verify if the data is reaching the LLM context properly

### Issue 2: Context Construction
- The `reduced_context` in `generate_report()` may not be properly formatting the PageSpeed data
- The LLM prompt expects specific data structure that may not match what's being provided

### Issue 3: LLM Processing
- The LLM may be receiving the data but not processing it correctly due to prompt issues
- Need to verify the actual JSON being sent to the LLM

## Debugging Steps Implemented

### 1. Added Debug Logging
Added comprehensive logging in `pipeline_service.py` to track:
- PageSpeed data type and structure
- Available keys in PageSpeed data
- Mobile/Desktop data availability
- Actual scores being passed

**Location**: `auditor_geo/backend/app/services/pipeline_service.py` lines ~1440

```python
# Debug logging for PageSpeed data
logger.info(f"PageSpeed data type: {type(pagespeed_data)}")
logger.info(f"PageSpeed data keys: {list(pagespeed_data.keys()) if pagespeed_data else 'None'}")
if pagespeed_data:
    logger.info(f"Mobile data available: {bool(pagespeed_data.get('mobile'))}")
    logger.info(f"Desktop data available: {bool(pagespeed_data.get('desktop'))}")
    if pagespeed_data.get('mobile'):
        logger.info(f"Mobile score: {pagespeed_data.get('mobile', {}).get('score')}")
```

### 2. Data Verification Points
- ✅ PageSpeed JSON file exists and contains valid data
- ✅ `audit.pagespeed_data` is loaded from database
- ✅ Data is passed to `generate_report()` method
- 🔍 **NEXT**: Verify data reaches LLM context correctly

## Expected Data Structure

### PageSpeed Data Format
```json
{
  "mobile": {
    "score": 55.0,
    "metrics": {
      "largest_contentful_paint": 10376.233,
      "interaction_to_next_paint": 390.0,
      "cumulative_layout_shift": 0.0,
      "first_contentful_paint": 2864.111
    },
    "opportunities": {
      "opportunity_name": {
        "title": "Optimize images",
        "numericValue": 1250,
        "description": "...",
        "score": 0.75
      }
    }
  },
  "desktop": { /* similar structure */ }
}
```

### Reduced Context Format
```json
{
  "pagespeed": {
    "mobile": {
      "score": 55.0,
      "lcp": 10376.233,
      "inp": 390.0,
      "cls": 0.0,
      "fcp": 2864.111,
      "top_3_opportunities": [
        {
          "id": "opportunity_name",
          "title": "Optimize images", 
          "savings_ms": 1250,
          "score": 0.75
        }
      ]
    },
    "desktop": { /* similar */ }
  }
}
```

## Next Steps

### 1. Monitor Debug Logs
Run a new PDF generation and check logs for:
- PageSpeed data structure
- Whether mobile/desktop data is available
- Actual scores being processed

### 2. Verify LLM Context
- Check if the `final_context_input` JSON contains proper PageSpeed data
- Ensure the LLM is receiving structured data, not empty objects

### 3. Prompt Optimization
If data is reaching the LLM but not being processed:
- Review the `REPORT_PROMPT_V11_COMPLETE` prompt
- Ensure it properly handles the PageSpeed data structure
- Add more specific instructions for data interpretation

### 4. Test with Known Good Data
- Create a test case with minimal but complete PageSpeed data
- Verify the entire pipeline works with controlled input

## Files Modified

1. **`auditor_geo/backend/app/services/pipeline_service.py`**
   - Added debug logging for PageSpeed data verification
   - Enhanced null handling in `_extract_top_opportunities()`

2. **`auditor_geo/backend/tests/test_pipeline_properties.py`**
   - Enhanced property-based tests for null handling

## Status

🔍 **IN PROGRESS** - Debug logging added, backend restarted, ready for testing

**Next Action**: Generate a new PDF for audit 65 and review the debug logs to identify where the data flow breaks.

## Test Command

To test the fix:
1. Generate a new PDF for audit 65
2. Check backend logs for debug information
3. Verify the generated PDF contains PageSpeed data
4. Review the `final_llm_context.json` for data completeness