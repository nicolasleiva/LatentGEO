"""
Property-based tests for pipeline_service.py

Tests correctness properties that should hold across all inputs.
"""

from app.services.pipeline_service import PipelineService
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

ASCII_TEXT = st.text(
    alphabet=st.characters(min_codepoint=32, max_codepoint=126),
    min_size=1,
    max_size=60,
)

OPPORTUNITY_KEY_POOL = [
    "largest-contentful-paint",
    "unused-css-rules",
    "unused-javascript",
    "render-blocking-resources",
    "server-response-time",
    "offscreen-images",
    "modern-image-formats",
    "total-byte-weight",
    "redirects",
    "dom-size",
]

VALID_OPPORTUNITY_DATA = st.fixed_dictionaries(
    {
        "title": ASCII_TEXT,
        "numericValue": st.one_of(
            st.integers(min_value=-1000, max_value=10000),
            st.floats(
                min_value=-1000,
                max_value=10000,
                allow_nan=False,
                allow_infinity=False,
                width=32,
            ),
            st.none(),
        ),
        "score": st.one_of(
            st.none(),
            st.floats(
                min_value=0,
                max_value=1,
                allow_nan=False,
                allow_infinity=False,
                width=32,
            ),
        ),
        "description": st.one_of(st.none(), st.text(max_size=80)),
        "displayValue": st.one_of(st.none(), st.text(max_size=30)),
    }
)

INVALID_OPPORTUNITY_DATA = st.one_of(
    st.none(),
    st.integers(),
    st.text(max_size=24),
    st.lists(st.text(max_size=12), max_size=3),
    st.booleans(),
)

COMPLEX_OPPORTUNITIES_DICT = st.dictionaries(
    keys=st.sampled_from(OPPORTUNITY_KEY_POOL),
    values=st.one_of(VALID_OPPORTUNITY_DATA, INVALID_OPPORTUNITY_DATA),
    min_size=0,
    max_size=10,
)

INVALID_OPPORTUNITIES_INPUT = st.one_of(
    st.none(),
    st.text(max_size=40),
    st.integers(),
    st.floats(allow_nan=False, allow_infinity=False, width=32),
    st.lists(st.integers(), max_size=6),
)


class TestPageSpeedOpportunitiesProperties:
    """Property-based tests for PageSpeed opportunities extraction."""

    @given(opportunities=COMPLEX_OPPORTUNITIES_DICT)
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_property_opportunities_extraction_never_crashes_for_complex_dicts(
        self, opportunities
    ):
        """
        Property 1: PageSpeed opportunities extraction is type-safe

        For any complex opportunities dictionary, extracting opportunities
        should never raise a TypeError and should always return a list.

        **Validates: Requirements 1.1, 1.2, 1.3**
        """
        # This should never crash, regardless of mixed valid/invalid values
        result = PipelineService._extract_top_opportunities(opportunities)

        # Always returns a list
        assert isinstance(result, list), f"Expected list, got {type(result)}"

        # Each item in the list should be a dict with expected keys
        for item in result:
            assert isinstance(item, dict)
            assert "id" in item
            assert "title" in item
            assert "savings_ms" in item
            assert isinstance(item["savings_ms"], (int, float))
            assert item["savings_ms"] > 0  # Only positive savings

    @given(opportunities=INVALID_OPPORTUNITIES_INPUT)
    @settings(max_examples=50, deadline=None)
    def test_property_opportunities_extraction_never_crashes_for_invalid_inputs(
        self, opportunities
    ):
        """
        Property 1b: Non-dict inputs are always handled safely.

        **Validates: Requirements 1.1, 1.2, 1.3**
        """
        result = PipelineService._extract_top_opportunities(opportunities)

        assert isinstance(result, list), f"Expected list, got {type(result)}"
        assert result == []

    @given(
        opportunities=st.dictionaries(
            keys=st.sampled_from(OPPORTUNITY_KEY_POOL),
            values=st.fixed_dictionaries(
                {
                    "title": ASCII_TEXT,
                    "numericValue": st.integers(min_value=1, max_value=10000),
                    "score": st.floats(
                        min_value=0,
                        max_value=1,
                        allow_nan=False,
                        allow_infinity=False,
                        width=32,
                    ),
                    "description": st.text(max_size=80),
                    "displayValue": st.text(max_size=30),
                }
            ),
            min_size=2,
            max_size=10,
        ),
        limit=st.integers(min_value=1, max_value=5),
    )
    @settings(max_examples=100, deadline=None)
    def test_property_opportunities_sorted_by_savings(self, opportunities, limit):
        """
        Property 2: Top opportunities are sorted by impact

        For any valid opportunities dictionary with numeric values, the extracted
        top opportunities list should be sorted in descending order by savings_ms.

        **Validates: Requirements 1.5**
        """
        result = PipelineService._extract_top_opportunities(opportunities, limit=limit)

        # Result should not exceed limit
        assert len(result) <= limit

        # Result should be sorted by savings_ms in descending order
        savings_values = [item["savings_ms"] for item in result]
        assert savings_values == sorted(
            savings_values, reverse=True
        ), f"Opportunities not sorted by savings: {savings_values}"

        # All savings should be positive
        assert all(s > 0 for s in savings_values)

    def test_opportunities_extraction_with_empty_dict(self):
        """Unit test: Empty dict returns empty list."""
        result = PipelineService._extract_top_opportunities({})
        assert result == []

    def test_opportunities_extraction_with_none(self):
        """Unit test: None returns empty list."""
        result = PipelineService._extract_top_opportunities(None)
        assert result == []

    def test_opportunities_extraction_filters_zero_savings(self):
        """Unit test: Opportunities with zero savings are filtered out."""
        opportunities = {
            "good_opp": {"title": "Good", "numericValue": 1000},
            "zero_opp": {"title": "Zero", "numericValue": 0},
            "negative_opp": {"title": "Negative", "numericValue": -100},
        }
        result = PipelineService._extract_top_opportunities(opportunities)

        assert len(result) == 1
        assert result[0]["id"] == "good_opp"
        assert result[0]["savings_ms"] == 1000

    def test_opportunities_extraction_with_malformed_data(self):
        """Unit test: Malformed opportunity data is skipped."""
        opportunities = {
            "valid": {"title": "Valid", "numericValue": 500},
            "invalid_string": "not a dict",
            "invalid_list": ["not", "a", "dict"],
            "missing_numeric": {"title": "Missing"},
            "valid2": {"title": "Valid 2", "numericValue": 300},
        }
        result = PipelineService._extract_top_opportunities(opportunities, limit=5)

        # Should only include the 2 valid opportunities
        assert len(result) == 2
        assert result[0]["savings_ms"] == 500  # Sorted descending
        assert result[1]["savings_ms"] == 300

    def test_opportunities_extraction_respects_limit(self):
        """Unit test: Result respects the limit parameter."""
        opportunities = {
            f"opp_{i}": {"title": f"Opp {i}", "numericValue": (10 - i) * 100}
            for i in range(10)
        }

        result = PipelineService._extract_top_opportunities(opportunities, limit=3)
        assert len(result) == 3

        result = PipelineService._extract_top_opportunities(opportunities, limit=7)
        assert len(result) == 7

    def test_opportunities_extraction_includes_all_fields(self):
        """Unit test: Result includes all expected fields."""
        opportunities = {
            "test_opp": {
                "title": "Test Opportunity",
                "numericValue": 1500,
                "score": 0.75,
                "description": "Test description",
                "displayValue": "1.5s",
            }
        }
        result = PipelineService._extract_top_opportunities(opportunities)

        assert len(result) == 1
        opp = result[0]

        assert opp["id"] == "test_opp"
        assert opp["title"] == "Test Opportunity"
        assert opp["savings_ms"] == 1500
        assert opp["score"] == 0.75
        assert opp["description"] == "Test description"
        assert opp["display_value"] == "1.5s"

    def test_opportunities_extraction_handles_null_numeric_values(self):
        """Unit test: Null numericValue is handled gracefully."""
        opportunities = {
            "null_numeric": {"title": "Null Numeric", "numericValue": None},
            "valid_numeric": {"title": "Valid Numeric", "numericValue": 1000},
            "missing_numeric": {"title": "Missing Numeric"},  # No numericValue key
        }
        result = PipelineService._extract_top_opportunities(opportunities)

        # Should only include the valid opportunity
        assert len(result) == 1
        assert result[0]["id"] == "valid_numeric"
        assert result[0]["savings_ms"] == 1000

    def test_opportunities_extraction_regression_mixed_payload(self):
        """
        Regression: mixed payload with malformed entries and nullable values
        should stay stable and preserve sorting.
        """
        opportunities = {
            "largest-contentful-paint": {
                "title": "Largest Contentful Paint",
                "numericValue": 500,
                "score": 0.41,
                "description": None,
                "displayValue": "0.5 s",
            },
            "unused-css": {
                "title": "Remove unused CSS",
                "numericValue": 845.5,
                "score": 0.7,
                "description": "Reduce transfer size.",
                "displayValue": "845 ms",
            },
            "bad-shape": ["not", "a", "dict"],
            "none-value": None,
            "negative-value": {"title": "Ignore negative", "numericValue": -15},
            "missing-numeric": {"title": "Missing numeric value"},
        }

        result = PipelineService._extract_top_opportunities(opportunities, limit=5)

        assert [item["id"] for item in result] == [
            "unused-css",
            "largest-contentful-paint",
        ]
