"""
GitHub OAuth Authentication Handler
"""

import secrets
from typing import Dict, Optional

import httpx
from cryptography.fernet import Fernet

from ...core.config import settings
from ...core.logger import get_logger

logger = get_logger(__name__)


class GitHubOAuth:
    """Maneja el flujo OAuth con GitHub"""

    # Scopes necesarios para la GitHub App
    SCOPES = [
        "repo",  # Acceso completo a repositorios
        "read:org",  # Leer info de organizaciones
        "write:discussion",  # Comentar en PRs
    ]

    @staticmethod
    def get_authorization_url(state: Optional[str] = None) -> Dict[str, str]:
        """
        Genera URL para iniciar OAuth flow

        Args:
            state: Token de seguridad (se genera automáticamente si no se proporciona)

        Returns:
            Dict con 'url' y 'state'
        """
        if not state:
            state = secrets.token_urlsafe(32)

        scopes = " ".join(GitHubOAuth.SCOPES)
        url = (
            f"https://github.com/login/oauth/authorize"
            f"?client_id={settings.GITHUB_CLIENT_ID}"
            f"&redirect_uri={settings.GITHUB_REDIRECT_URI}"
            f"&scope={scopes}"
            f"&state={state}"
            f"&prompt=login"
        )

        return {"url": url, "state": state}

    @staticmethod
    async def exchange_code(code: str) -> Dict:
        """
        Intercambia código de autorización por access token

        Args:
            code: Código de autorización de GitHub

        Returns:
            Dict con token data

        Raises:
            Exception si el exchange falla
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    "https://github.com/login/oauth/access_token",
                    data={
                        "client_id": settings.GITHUB_CLIENT_ID,
                        "client_secret": settings.GITHUB_CLIENT_SECRET,
                        "code": code,
                        "redirect_uri": settings.GITHUB_REDIRECT_URI,
                    },
                    headers={"Accept": "application/json"},
                )
                response.raise_for_status()
                data = response.json()

                if "error" in data:
                    raise Exception(
                        f"GitHub OAuth error: {data.get('error_description', data['error'])}"
                    )

                logger.info("GitHub OAuth token exchange successful")
                return data

            except httpx.HTTPStatusError as e:
                logger.error(f"GitHub OAuth exchange failed: {e}")
                raise Exception(f"Failed to exchange code: {e}")

    @staticmethod
    async def get_user_info(access_token: str) -> Dict:
        """
        Obtiene información del usuario autenticado

        Args:
            access_token: Token de acceso de GitHub

        Returns:
            Dict con info del usuario
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.github.com/user",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
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

    @staticmethod
    async def revoke_token(access_token: str) -> bool:
        """
        Revoca un access token (para logout/desconexión)

        Args:
            access_token: Token a revocar

        Returns:
            True si fue exitoso
        """
        async with httpx.AsyncClient() as client:
            try:
                # GitHub requiere autenticación básica para revocar tokens
                import base64

                auth = base64.b64encode(
                    f"{settings.GITHUB_CLIENT_ID}:{settings.GITHUB_CLIENT_SECRET}".encode()
                ).decode()

                response = await client.delete(
                    f"https://api.github.com/applications/{settings.GITHUB_CLIENT_ID}/token",
                    headers={
                        "Authorization": f"Basic {auth}",
                        "Accept": "application/vnd.github+json",
                    },
                    json={"access_token": access_token},
                )

                return response.status_code == 204

            except Exception as e:
                logger.error(f"Failed to revoke GitHub token: {e}")
                return False
