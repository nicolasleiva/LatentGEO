# PDF Generation Null Handling Fix

## Issue Description

After the initial PDF generation fixes, a new TypeError was discovered:

```
TypeError: '>' not supported between instances of 'NoneType' and 'int'
```

This occurred in `pipeline_service.py` at line 584 when trying to compare `numeric_value > 0` where `numeric_value` was `None`.

## Root Cause

The issue was in the `_extract_top_opportunities()` method where:

```python
numeric_value = opp_data.get("numericValue", 0)
if numeric_value > 0:  # This failed when numeric_value was None
```

The problem occurs when the PageSpeed API returns opportunities with explicit `null` values for `numericValue`. The `.get()` method with a default value only applies when the key is missing, not when the key exists but has a `None` value.

## Solution

Added comprehensive null and type checking before the comparison:

```python
# Extract numeric value (savings in ms)
numeric_value = opp_data.get("numericValue", 0)
# Handle None values explicitly
if numeric_value is None:
    logger.debug(f"Found None numericValue for opportunity {key}, converting to 0")
    numeric_value = 0

# Additional type checking for safety
if not isinstance(numeric_value, (int, float)):
    logger.warning(f"Invalid numericValue type for {key}: {type(numeric_value)} = {numeric_value}, converting to 0")
    numeric_value = 0
    
if numeric_value > 0:  # Only include opportunities with measurable savings
```

## Testing

Added comprehensive tests to prevent regression:

1. **Unit Test**: `test_opportunities_extraction_handles_null_numeric_values()`
   - Tests explicit null handling for `numericValue: None`
   - Verifies that null values are filtered out correctly

2. **Property-Based Test Enhancement**: 
   - Added `st.none()` to the hypothesis strategy
   - Ensures null values are handled across all possible input combinations

## Files Modified

- `auditor_geo/backend/app/services/pipeline_service.py` - Added null checking
- `auditor_geo/backend/tests/test_pipeline_properties.py` - Enhanced tests

## Verification

1. Backend rebuilt and restarted successfully with `docker-compose build backend && docker-compose up -d backend`
2. Enhanced fix handles all edge cases:
   - Missing `numericValue` key → defaults to 0
   - Explicit `numericValue: null` → converted to 0 with debug log
   - Invalid types (strings, objects, etc.) → converted to 0 with warning log
   - Valid `numericValue: 1000` → used as-is

## Status

✅ **FIXED** - PDF generation now handles all PageSpeed numeric value edge cases gracefully with comprehensive logging.

The system is ready for testing with audit ID 65 or any new audits. The enhanced logging will help identify any remaining data quality issues.