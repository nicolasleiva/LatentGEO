from typing import Dict, Optional

import httpx
from cryptography.fernet import Fernet

from ...core.config import settings


class HubSpotAuth:
    """Maneja el flujo OAuth con HubSpot"""

    # Scopes necesarios para leer/escribir páginas
    SCOPES = [
        "content",
        "cms.pages.write",
        "cms.pages.read",
    ]

    @staticmethod
    def get_authorization_url(state: Optional[str] = None) -> str:
        """Genera URL para iniciar OAuth"""
        scopes = " ".join(HubSpotAuth.SCOPES)
        url = (
            f"https://app.hubspot.com/oauth/authorize"
            f"?client_id={settings.HUBSPOT_CLIENT_ID}"
            f"&redirect_uri={settings.HUBSPOT_REDIRECT_URI}"
            f"&scope={scopes}"
        )
        if state:
            url += f"&state={state}"
        return url

    @staticmethod
    async def exchange_code(code: str) -> Dict:
        """Intercambia código de autorización por access token"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.hubapi.com/oauth/v1/token",
                data={
                    "grant_type": "authorization_code",
                    "client_id": settings.HUBSPOT_CLIENT_ID,
                    "client_secret": settings.HUBSPOT_CLIENT_SECRET,
                    "redirect_uri": settings.HUBSPOT_REDIRECT_URI,
                    "code": code,
                },
            )
            response.raise_for_status()
            return response.json()

    @staticmethod
    async def refresh_token(refresh_token: str) -> Dict:
        """Refresca el access token usando el refresh token"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.hubapi.com/oauth/v1/token",
                data={
                    "grant_type": "refresh_token",
                    "client_id": settings.HUBSPOT_CLIENT_ID,
                    "client_secret": settings.HUBSPOT_CLIENT_SECRET,
                    "refresh_token": refresh_token,
                },
            )
            response.raise_for_status()
            return response.json()

    @staticmethod
    def encrypt_token(token: str) -> str:
        """Encripta un token para guardarlo en DB"""
        if not token:
            return ""
        cipher = Fernet(settings.ENCRYPTION_KEY.encode())
        return cipher.encrypt(token.encode()).decode()

    @staticmethod
    def decrypt_token(encrypted_token: str) -> str:
        """Desencripta un token"""
        if not encrypted_token:
            return ""
        cipher = Fernet(settings.ENCRYPTION_KEY.encode())
        return cipher.decrypt(encrypted_token.encode()).decode()
