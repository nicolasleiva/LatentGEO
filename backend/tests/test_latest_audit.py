import json

from app.models import Audit


def test_latest_audit(db_session):
    """Test para obtener la auditoría más reciente"""
    # Crear una auditoría de prueba
    test_pagespeed_data = {
        "mobile": {"performance_score": 85},
        "desktop": {"performance_score": 90},
    }

    audit = Audit(
        url="https://example.com",
        status="completed",
        pagespeed_data=json.dumps(test_pagespeed_data),
    )
    db_session.add(audit)
    db_session.commit()

    # Obtener la última auditoría
    latest_audit = db_session.query(Audit).order_by(Audit.id.desc()).first()

    assert latest_audit is not None
    assert latest_audit.url == "https://example.com"
    assert latest_audit.status == "completed"

    if latest_audit.pagespeed_data:
        data = json.loads(latest_audit.pagespeed_data)
        assert "mobile" in data
        assert data["mobile"]["performance_score"] == 85
