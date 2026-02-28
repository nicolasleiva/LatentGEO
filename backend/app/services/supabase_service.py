"""
Servicio de integración con Supabase (Storage & Auth Admin)
"""

from typing import Optional

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

# Intentar importar supabase, manejar fallo si no está instalado (durante migración)
try:
    from supabase import Client, create_client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    logger.warning("Supabase client library not found. Install 'supabase' package.")


class SupabaseService:
    """Servicio wrapper para Supabase"""

    _client: Optional["Client"] = None

    @classmethod
    def get_client(cls) -> "Client":
        """Obtener cliente singleton de Supabase (Service Role)"""
        if not SUPABASE_AVAILABLE:
            raise ImportError("Librería 'supabase' no instalada.")
        
        if cls._client is None:
            if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
                raise ValueError(
                    "SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY son requeridos para operaciones de backend."
                )
            cls._client = create_client(
                settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY
            )
        return cls._client

    @classmethod
    def upload_file(
        cls, 
        bucket: str, 
        path: str, 
        file_content: bytes, 
        content_type: str = "application/pdf"
    ) -> str:
        """
        Subir archivo a Supabase Storage.
        Retorna el path del archivo almacenado.
        """
        client = cls.get_client()
        try:
            # Upsert para sobrescribir si existe
            client.storage.from_(bucket).upload(
                path=path,
                file=file_content,
                file_options={"content-type": content_type, "upsert": "true"}
            )
            logger.info(f"Archivo subido a Supabase Storage: {bucket}/{path}")
            return path
        except Exception as e:
            logger.error(f"Error subiendo archivo a Supabase: {e}")
            raise e

    @classmethod
    def get_signed_url(cls, bucket: str, path: str, expiry_seconds: int = 3600) -> str:
        """Generar URL firmada para descarga segura"""
        client = cls.get_client()
        try:
            # create_signed_url retorna str o dict dependiendo de la versión/implementación
            # Asumimos que la librería oficial retorna el JSON response
            res = client.storage.from_(bucket).create_signed_url(path, expiry_seconds)
            
            # En supabase-py v2, create_signed_url retorna un dict con 'signedURL'
            if isinstance(res, dict) and "signedURL" in res:
                return res["signedURL"]
            # Fallback por si cambia la API
            return str(res)
        except Exception as e:
            logger.error(f"Error generando signed URL: {e}")
            raise e

    @classmethod
    def delete_file(cls, bucket: str, path: str):
        """Eliminar archivo"""
        client = cls.get_client()
        try:
            client.storage.from_(bucket).remove([path])
        except Exception as e:
            logger.error(f"Error eliminando archivo de Supabase: {e}")
            # No lanzamos error para no interrumpir flujos de limpieza

    @classmethod
    def ensure_bucket_exists(cls, bucket: str, public: bool = False):
        """Asegurar que el bucket exista, crearlo si no"""
        client = cls.get_client()
        try:
            buckets = client.storage.list_buckets()
            exists = any(b.name == bucket for b in buckets)
            
            if not exists:
                logger.info(f"Creando bucket Supabase: {bucket}")
                client.storage.create_bucket(bucket, options={"public": public})
            else:
                logger.info(f"Bucket Supabase ya existe: {bucket}")
        except Exception as e:
            logger.error(f"Error verificando/creando bucket: {e}")
            # No bloqueamos, puede ser falta de permisos admin pero el bucket ya existir
