import json
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core import auth as auth_module
from app.core.auth import get_user_from_bearer_token
from fastapi import HTTPException


def _build_rsa_fixture():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
    public_jwk["kid"] = "test-kid"
    public_jwk["alg"] = "RS256"
    public_jwk["use"] = "sig"
    return private_key, public_jwk


def _build_token(
    private_key,
    *,
    sub: str = "auth0|user-1",
    aud: str = "https://api.example.com",
    iss: str = "https://tenant.auth0.com/",
    azp: str | None = None,
):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "email": "test@example.com",
        "aud": aud,
        "iss": iss,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=10)).timestamp()),
    }
    if azp:
        payload["azp"] = azp
    return jwt.encode(
        payload,
        private_key,
        algorithm="RS256",
        headers={"kid": "test-kid"},
    )


def _set_auth0_settings(monkeypatch):
    monkeypatch.setattr(
        auth_module.settings,
        "AUTH0_ISSUER_BASE_URL",
        "https://tenant.auth0.com/",
        raising=False,
    )
    monkeypatch.setattr(
        auth_module.settings,
        "AUTH0_API_AUDIENCE",
        "https://api.example.com",
        raising=False,
    )
    monkeypatch.setattr(
        auth_module.settings,
        "AUTH0_EXPECTED_CLIENT_ID",
        None,
        raising=False,
    )
    monkeypatch.setattr(auth_module.settings, "ENVIRONMENT", "development", raising=False)


def test_accepts_valid_auth0_access_token(monkeypatch):
    _set_auth0_settings(monkeypatch)
    private_key, public_jwk = _build_rsa_fixture()
    monkeypatch.setattr(auth_module, "_get_jwk_for_kid", lambda *_: public_jwk)

    token = _build_token(private_key)
    user = get_user_from_bearer_token(token)
    assert user.user_id == "auth0|user-1"
    assert user.email == "test@example.com"


def test_rejects_invalid_audience(monkeypatch):
    _set_auth0_settings(monkeypatch)
    private_key, public_jwk = _build_rsa_fixture()
    monkeypatch.setattr(auth_module, "_get_jwk_for_kid", lambda *_: public_jwk)

    token = _build_token(private_key, aud="https://wrong-audience.example.com")

    with pytest.raises(HTTPException) as exc_info:
        get_user_from_bearer_token(token)

    assert exc_info.value.status_code == 401
    assert exc_info.value.headers.get("X-Auth-Error-Code") == "invalid_audience"


def test_rejects_invalid_issuer(monkeypatch):
    _set_auth0_settings(monkeypatch)
    private_key, public_jwk = _build_rsa_fixture()
    monkeypatch.setattr(auth_module, "_get_jwk_for_kid", lambda *_: public_jwk)

    token = _build_token(private_key, iss="https://another-issuer.auth0.com/")

    with pytest.raises(HTTPException) as exc_info:
        get_user_from_bearer_token(token)

    assert exc_info.value.status_code == 401
    assert exc_info.value.headers.get("X-Auth-Error-Code") == "invalid_issuer"


def test_rejects_unexpected_client_id_when_configured(monkeypatch):
    _set_auth0_settings(monkeypatch)
    monkeypatch.setattr(
        auth_module.settings,
        "AUTH0_EXPECTED_CLIENT_ID",
        "allowed-client-id",
        raising=False,
    )

    private_key, public_jwk = _build_rsa_fixture()
    monkeypatch.setattr(auth_module, "_get_jwk_for_kid", lambda *_: public_jwk)

    token = _build_token(private_key, azp="different-client-id")

    with pytest.raises(HTTPException) as exc_info:
        get_user_from_bearer_token(token)

    assert exc_info.value.status_code == 401
    assert exc_info.value.headers.get("X-Auth-Error-Code") == "invalid_client"
