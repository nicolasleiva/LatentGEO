"""
Tests para el API de Auditorías
"""

from unittest.mock import MagicMock, patch

from app.schemas import AuditStatus
from fastapi.testclient import TestClient


def test_create_audit_dispatches_task(client: TestClient):
    """
    Verifica que al crear una auditoría:
    1. Se retorna un estado 201 CREATED.
    2. El estado de la auditoría es PENDING.
    3. Se despacha una tarea de Celery 'run_audit_task'.
    """
    # Mock de la tarea de Celery
    with patch("app.api.routes.audits.run_audit_task.delay") as mock_delay:
        mock_task = MagicMock()
        mock_task.id = "test-task-id"
        mock_delay.return_value = mock_task

        # Datos para la nueva auditoría
        audit_data = {
            "url": "https://ceibo.digital",
            "max_crawl": 10,
            "max_audit": 2,
            "market": "AR",
        }

        # Realizar la petición
        response = client.post("/api/audits/", json=audit_data)

        # 1. Verificar estado de la respuesta
        assert response.status_code == 202

        response_data = response.json()

        # 2. Verificar que el estado es PENDING
        assert response_data["status"] == AuditStatus.PENDING.value
        assert "id" in response_data

        audit_id = response_data["id"]

        # 3. Verificar que la tarea de Celery fue llamada
        mock_delay.assert_called_once_with(audit_id)


def test_get_audits_list(client: TestClient):
    """
    Verifica que se puede obtener una lista de auditorías.
    """
    response = client.get("/api/audits/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
