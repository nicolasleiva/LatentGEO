
import os
import sys
import logging
import uuid
from dotenv import load_dotenv

# Cargar .env
load_dotenv()

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_supabase")

def test_supabase_connection():
    try:
        from supabase import create_client
    except ImportError:
        logger.error("Supabase library not installed. Run: pip install supabase")
        return

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not url or not key:
        logger.error("Faltan credenciales SUPABASE_URL o SUPABASE_KEY en .env")
        return

    logger.info(f"Probando conexión a: {url}")
    
    # 1. Probar Cliente Anon (Lectura pública si permitido)
    try:
        supabase_anon = create_client(url, key)
        logger.info("Cliente Anon inicializado.")
    except Exception as e:
        logger.error(f"Error inicializando cliente Anon: {e}")
        return

    bucket_name = os.getenv("SUPABASE_STORAGE_BUCKET", "audit-reports")
    test_filename = f"test_file_{uuid.uuid4()}.txt"
    test_content = b"Hello Supabase from Auditor GEO!"

    # 2. Intentar subir archivo
    # Usamos la Service Role Key si es diferente a la Anon Key, sino intentamos con lo que hay
    # Nota: Si key == service_role_key y es la anon key, fallará si RLS requiere 'authenticated' y no 'anon'
    
    upload_client = supabase_anon
    client_type = "Anon"
    
    if service_role_key and service_role_key != key:
        try:
            upload_client = create_client(url, service_role_key)
            client_type = "Service Role"
            logger.info("Usando Service Role Key para la prueba de escritura.")
        except Exception as e:
            logger.warning(f"No se pudo inicializar cliente Service Role: {e}")
    else:
        logger.warning("Service Role Key no configurada o igual a Anon Key. Probando upload como Anon/Public...")

    logger.info(f"Intentando subir archivo '{test_filename}' al bucket '{bucket_name}' usando cliente {client_type}...")
    
    try:
        res = upload_client.storage.from_(bucket_name).upload(
            path=test_filename,
            file=test_content,
            file_options={"content-type": "text/plain"}
        )
        logger.info(f"✅ Subida exitosa! Respuesta: {res}")
        
        # 3. Intentar descargar/verificar
        logger.info("Verificando archivo subido...")
        list_res = upload_client.storage.from_(bucket_name).list()
        files = [x['name'] for x in list_res]
        if test_filename in files:
            logger.info(f"✅ Archivo encontrado en el bucket: {test_filename}")
            
            # Limpieza
            logger.info("Eliminando archivo de prueba...")
            upload_client.storage.from_(bucket_name).remove([test_filename])
            logger.info("✅ Limpieza completada.")
        else:
            logger.warning("⚠️ El archivo se subió pero no aparece en la lista (posible latencia o RLS de lectura).")

    except Exception as e:
        logger.error(f"❌ Fallo la subida de archivo: {e}")
        logger.info("\n--- DIAGNÓSTICO ---")
        if "new row violates row-level security policy" in str(e) or "403" in str(e):
            logger.error("BLOQUEO DE SEGURIDAD (RLS):")
            logger.error("El bucket existe, pero tu clave actual no tiene permisos para escribir.")
            logger.error("Causa probable: Estás usando la 'Anon Key' pero la política requiere 'Authenticated' o 'Service Role'.")
            logger.error("Solución 1 (Recomendada): Consigue la 'service_role key' de Supabase (Settings > API) y ponla en .env como SUPABASE_SERVICE_ROLE_KEY.")
            logger.error("Solución 2 (Insegura): Edita la política en Supabase para permitir INSERT a la role 'anon'.")
        elif "The resource was not found" in str(e) or "404" in str(e):
            logger.error("BUCKET NO ENCONTRADO:")
            logger.error(f"Asegúrate de que el bucket '{bucket_name}' exista exactamente con ese nombre.")

if __name__ == "__main__":
    test_supabase_connection()
