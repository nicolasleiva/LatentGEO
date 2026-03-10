from cryptography.fernet import Fernet, InvalidToken

from ...core.config import settings


class OdooAuth:
    @staticmethod
    def encrypt_api_key(api_key: str) -> str:
        cipher = Fernet(settings.ENCRYPTION_KEY.encode())
        return cipher.encrypt(api_key.encode()).decode()

    @staticmethod
    def decrypt_api_key(encrypted_api_key: str) -> str:
        if not encrypted_api_key:
            return ""
        try:
            cipher = Fernet(settings.ENCRYPTION_KEY.encode())
            return cipher.decrypt(encrypted_api_key.encode()).decode()
        except (InvalidToken, TypeError, ValueError):
            return ""
