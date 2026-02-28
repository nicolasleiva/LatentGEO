from app.main import create_app


PUBLIC_OPERATIONS = (
    ("post", "/api/v1/github/webhook"),
    ("post", "/api/v1/webhooks/github/incoming"),
    ("post", "/api/v1/webhooks/hubspot/incoming"),
    ("get", "/health"),
    ("get", "/health/ready"),
    ("get", "/health/live"),
)


def test_openapi_security_contract_keeps_public_overrides():
    app = create_app()
    schema = app.openapi()

    assert schema["security"] == [{"HTTPBearer": []}]
    assert schema["components"]["securitySchemes"]["HTTPBearer"] == {
        "type": "http",
        "scheme": "bearer",
    }

    for method, path in PUBLIC_OPERATIONS:
        operation = schema["paths"][path][method]
        assert operation["security"] == []

    private_operation = schema["paths"]["/api/v1/geo/dashboard/{audit_id}"]["get"]
    assert private_operation["security"] == [{"HTTPBearer": []}]


def test_openapi_security_is_explicit_for_every_operation():
    app = create_app()
    schema = app.openapi()

    http_methods = {"get", "post", "put", "patch", "delete", "options", "head", "trace"}
    for path_item in schema["paths"].values():
        for method, operation in path_item.items():
            if method.lower() not in http_methods:
                continue
            assert "security" in operation
