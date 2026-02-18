from app.services.audit_service import CompetitorService


def test_geo_score_with_full_signals():
    audit_data = {
        "schema": {"schema_presence": {"status": "present"}},
        "structure": {
            "semantic_html": {"score_percent": 60},
            "h1_check": {"status": "pass"},
        },
        "eeat": {"author_presence": {"status": "pass"}},
        "content": {"conversational_tone": {"score": 6}},
    }
    score = CompetitorService._calculate_geo_score(audit_data)
    assert score == 86.0


def test_geo_score_with_partial_signals():
    audit_data = {
        "structure": {"semantic_html": {"score_percent": 50}},
        "content": {"conversational_tone": {"score": 2}},
    }
    score = CompetitorService._calculate_geo_score(audit_data)
    assert score == 37.1


def test_geo_score_with_no_signals():
    score = CompetitorService._calculate_geo_score({})
    assert score == 0.0


def test_geo_score_site_metrics_avoids_double_counting_h1():
    audit_data = {
        "site_metrics": {"structure_score_percent": 80},
        "structure": {"h1_check": {"status": "fail"}},
    }
    score = CompetitorService._calculate_geo_score(audit_data)
    assert score == 80.0
