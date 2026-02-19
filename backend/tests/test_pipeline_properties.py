"""
Property-based tests for pipeline_service.py

Tests correctness properties that should hold across all inputs.
"""

from app.services.pipeline_service import PipelineService
from hypothesis import given, settings
from hypothesis import strategies as st


class TestPageSpeedOpportunitiesProperties:
    """Property-based tests for PageSpeed opportunities extraction."""

    @given(
        opportunities=st.one_of(
            st.none(),
            st.just({}),
            st.dictionaries(
                keys=st.text(min_size=1, max_size=50),
                values=st.dictionaries(
                    keys=st.sampled_from(
                        [
                            "title",
                            "numericValue",
                            "score",
                            "description",
                            "displayValue",
                        ]
                    ),
                    values=st.one_of(
                        st.text(max_size=100),
                        st.integers(min_value=0, max_value=10000),
                        st.floats(
                            min_value=0,
                            max_value=1,
                            allow_nan=False,
                            allow_infinity=False,
                        ),
                        st.none(),  # Include None values to test null handling
                    ),
                    min_size=0,
                    max_size=5,
                ),
                min_size=0,
                max_size=20,
            ),
            st.lists(st.text()),  # Invalid: list instead of dict
            st.text(),  # Invalid: string instead of dict
            st.integers(),  # Invalid: int instead of dict
        )
    )
    @settings(max_examples=100, deadline=None)
    def test_property_opportunities_extraction_never_crashes(self, opportunities):
        """
        Property 1: PageSpeed opportunities extraction is type-safe

        For any input (dict, None, list, string, etc.), extracting opportunities
        should never raise a TypeError and should always return a list.

        **Validates: Requirements 1.1, 1.2, 1.3**
        """
        # This should never crash, regardless of input
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

    @given(
        opportunities=st.dictionaries(
            keys=st.text(min_size=1, max_size=50),
            values=st.fixed_dictionaries(
                {
                    "title": st.text(min_size=1, max_size=100),
                    "numericValue": st.integers(min_value=1, max_value=10000),
                    "score": st.floats(
                        min_value=0, max_value=1, allow_nan=False, allow_infinity=False
                    ),
                    "description": st.text(max_size=200),
                    "displayValue": st.text(max_size=50),
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
