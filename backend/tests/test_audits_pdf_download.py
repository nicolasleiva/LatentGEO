from app.core.config import settings
from app.models import Audit, AuditStatus, Report


def _create_completed_audit(db_session, file_path: str = "supabase://audits/3/report.pdf"):
    audit = Audit(
        url="https://www.robot.com/",
        domain="www.robot.com",
        status=AuditStatus.COMPLETED,
        progress=100.0,
        user_id="test-user",
        user_email="test@example.com",
    )
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)

    report = Report(
        audit_id=audit.id,
        report_type="PDF",
        file_path=file_path,
    )
    db_session.add(report)
    db_session.commit()
    return audit


def test_download_pdf_url_returns_signed_url(client, db_session, monkeypatch):
    audit = _create_completed_audit(db_session)

    monkeypatch.setattr(
        "app.services.supabase_service.SupabaseService.get_signed_url",
        lambda bucket, path, expiry_seconds=3600: "https://project.supabase.co/storage/v1/object/sign/audit-reports/audits/3/report.pdf?token=test",
    )

    response = client.get(f"/api/v1/audits/{audit.id}/download-pdf-url")

    assert response.status_code == 200
    payload = response.json()
    assert payload["download_url"].startswith("https://project.supabase.co/")
    assert payload["expires_in_seconds"] == 3600
    assert payload["storage_provider"] == "supabase"


def test_download_pdf_redirect_returns_302_with_location(client, db_session, monkeypatch):
    audit = _create_completed_audit(db_session)

    signed_url = "https://project.supabase.co/storage/v1/object/sign/audit-reports/audits/3/report.pdf?token=test"
    monkeypatch.setattr(
        "app.services.supabase_service.SupabaseService.get_signed_url",
        lambda bucket, path, expiry_seconds=3600: signed_url,
    )

    response = client.get(
        f"/api/v1/audits/{audit.id}/download-pdf",
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers.get("location") == signed_url


def test_download_pdf_url_normalizes_relative_signed_url(client, db_session, monkeypatch):
    audit = _create_completed_audit(db_session)

    class _BucketClient:
        def create_signed_url(self, path, expiry_seconds):
            return {"signedURL": "/storage/v1/object/sign/audit-reports/audits/3/report.pdf?token=test"}

    class _StorageClient:
        def from_(self, bucket):
            return _BucketClient()

    class _SupabaseClient:
        storage = _StorageClient()

    monkeypatch.setattr("app.services.supabase_service.SUPABASE_AVAILABLE", True)
    monkeypatch.setattr(
        "app.services.supabase_service.SupabaseService._client",
        _SupabaseClient(),
    )
    monkeypatch.setattr(
        settings,
        "SUPABASE_URL",
        "https://project.supabase.co",
        raising=False,
    )

    response = client.get(f"/api/v1/audits/{audit.id}/download-pdf-url")

    assert response.status_code == 200
    payload = response.json()
    assert payload["download_url"].startswith("https://project.supabase.co/storage/v1/object/sign/")


def test_download_pdf_url_returns_409_for_legacy_local_path(client, db_session):
    audit = _create_completed_audit(db_session, file_path="/tmp/report.pdf")

    response = client.get(f"/api/v1/audits/{audit.id}/download-pdf-url")

    assert response.status_code == 409
    assert "Legacy local PDF paths are disabled" in response.json()["detail"]
