#!/usr/bin/env python3
"""
Script para validar que todas las variables de entorno necesarias estén configuradas.
Ejecutar antes de desplegar a producción.
"""
import os
from pathlib import Path
from typing import List, Tuple

# Colores para output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

def check_env_file() -> Tuple[bool, List[str]]:
    """Verificar que existe el archivo .env"""
    env_path = Path('.env')
    if not env_path.exists():
        return False, ["[X] Archivo .env no encontrado en el directorio raiz"]
    return True, [f"[OK] Archivo .env encontrado: {env_path.absolute()}"]

def load_env_file() -> dict:
    """Cargar variables del archivo .env"""
    env_vars = {}
    env_path = Path('.env')
    
    if env_path.exists():
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # Ignorar comentarios y líneas vacías
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
    return env_vars

def check_variables(env_vars: dict) -> Tuple[List[str], List[str], List[str]]:
    """Verificar variables de entorno"""
    errors = []
    warnings = []
    info = []
    
    # Variables CRÍTICAS (la app no funcionará sin ellas)
    critical_vars = {
        'DATABASE_URL': 'URL de conexión a la base de datos',
        'SECRET_KEY': 'Clave secreta para seguridad (mínimo 32 caracteres)',
    }
    
    # Variables IMPORTANTES (funcionalidades limitadas sin ellas)
    important_vars = {
        'REDIS_URL': 'URL de Redis para cache y tareas asíncronas',
        'NVIDIA_API_KEY': 'API key de NVIDIA para análisis con IA',
        'NV_API_KEY_ANALYSIS': 'API key de NVIDIA para análisis (opcional)',
        'NV_API_KEY_CODE': 'API key de NVIDIA para generación de código (opcional)',
        'GOOGLE_PAGESPEED_API_KEY': 'API key de Google PageSpeed',
    }
    
    # Variables OPCIONALES (mejoran funcionalidades)
    optional_vars = {
        'GEMINI_API_KEY': 'API key de Gemini (alternativa a NVIDIA)',
        'GOOGLE_API_KEY': 'API key de Google para búsquedas',
        'CSE_ID': 'ID de Custom Search Engine de Google',
        'SENTRY_DSN': 'DSN de Sentry para monitoreo de errores',
        'ENCRYPTION_KEY': 'Clave de encriptación para tokens OAuth (32 bytes)',
        'WEBHOOK_SECRET': 'Secreto para validar webhooks',
        'FRONTEND_URL': 'URL del frontend en producción',
        'CORS_ORIGINS': 'Orígenes permitidos para CORS (separados por coma)',
        'TRUSTED_HOSTS': 'Hosts confiables (separados por coma)',
    }
    
    # Variables de integración
    integration_vars = {
        'AUTH0_SECRET': 'Secreto de Auth0',
        'AUTH0_DOMAIN': 'Dominio de Auth0',
        'AUTH0_CLIENT_ID': 'Client ID de Auth0',
        'AUTH0_CLIENT_SECRET': 'Client Secret de Auth0',
        'HUBSPOT_CLIENT_ID': 'Client ID de HubSpot',
        'HUBSPOT_CLIENT_SECRET': 'Client Secret de HubSpot',
        'HUBSPOT_REDIRECT_URI': 'URI de redirección de HubSpot',
        'GITHUB_CLIENT_ID': 'Client ID de GitHub',
        'GITHUB_CLIENT_SECRET': 'Client Secret de GitHub',
        'GITHUB_REDIRECT_URI': 'URI de redirección de GitHub',
    }
    
    # Verificar variables críticas
    for var, description in critical_vars.items():
        value = env_vars.get(var, '')
        if not value:
            errors.append(f"[X] {var}: FALTANTE - {description}")
        elif var == 'SECRET_KEY' and value == 'your-secret-key-change-in-production':
            errors.append(f"[X] {var}: VALOR POR DEFECTO - Debes cambiar este valor en produccion")
        elif var == 'SECRET_KEY' and len(value) < 32:
            warnings.append(f"[!] {var}: Muy corta (minimo 32 caracteres recomendado)")
        else:
            info.append(f"[OK] {var}: Configurada")
    
    # Verificar variables importantes
    for var, description in important_vars.items():
        value = env_vars.get(var, '')
        if not value:
            warnings.append(f"[!] {var}: No configurada - {description}")
        else:
            info.append(f"[OK] {var}: Configurada")
    
    # Verificar variables opcionales
    for var, description in optional_vars.items():
        value = env_vars.get(var, '')
        if value:
            info.append(f"[OK] {var}: Configurada")
        # No agregamos warning para opcionales
    
    # Verificar variables de integración (solo si están parcialmente configuradas)
    auth0_vars = ['AUTH0_SECRET', 'AUTH0_DOMAIN', 'AUTH0_CLIENT_ID', 'AUTH0_CLIENT_SECRET']
    auth0_configured = [v for v in auth0_vars if env_vars.get(v)]
    if auth0_configured and len(auth0_configured) < len(auth0_vars):
        warnings.append(f"[!] Auth0: Configuracion incompleta ({len(auth0_configured)}/{len(auth0_vars)} variables)")
    elif len(auth0_configured) == len(auth0_vars):
        info.append(f"[OK] Auth0: Completamente configurado")
    
    hubspot_vars = ['HUBSPOT_CLIENT_ID', 'HUBSPOT_CLIENT_SECRET']
    hubspot_configured = [v for v in hubspot_vars if env_vars.get(v)]
    if hubspot_configured and len(hubspot_configured) < len(hubspot_vars):
        warnings.append(f"[!] HubSpot: Configuracion incompleta ({len(hubspot_configured)}/{len(hubspot_vars)} variables)")
    elif len(hubspot_configured) == len(hubspot_vars):
        info.append(f"[OK] HubSpot: Completamente configurado")
    
    github_vars = ['GITHUB_CLIENT_ID', 'GITHUB_CLIENT_SECRET']
    github_configured = [v for v in github_vars if env_vars.get(v)]
    if github_configured and len(github_configured) < len(github_vars):
        warnings.append(f"[!] GitHub: Configuracion incompleta ({len(github_configured)}/{len(github_vars)} variables)")
    elif len(github_configured) == len(github_vars):
        info.append(f"[OK] GitHub: Completamente configurado")
    
    # Verificar ENCRYPTION_KEY si hay integraciones
    if (hubspot_configured or github_configured) and not env_vars.get('ENCRYPTION_KEY'):
        errors.append("[X] ENCRYPTION_KEY: REQUERIDA cuando hay integraciones configuradas")
    elif env_vars.get('ENCRYPTION_KEY') == 'your-encryption-key-must-be-32-url-safe-base64-bytes':
        errors.append("[X] ENCRYPTION_KEY: VALOR POR DEFECTO - Debes cambiar este valor")
    
    # Verificar configuración de producción
    debug = env_vars.get('DEBUG', 'False').lower()
    environment = env_vars.get('ENVIRONMENT', 'development').lower()
    
    if environment == 'production':
        if debug == 'true':
            warnings.append("[!] DEBUG=True en produccion - Deberia ser False")
        if not env_vars.get('FRONTEND_URL') or 'localhost' in env_vars.get('FRONTEND_URL', ''):
            warnings.append("[!] FRONTEND_URL: Contiene localhost en produccion")
        if not env_vars.get('CORS_ORIGINS'):
            warnings.append("[!] CORS_ORIGINS: No configurado - Usara valores por defecto")
    
    return errors, warnings, info

def main():
    import sys
    # Configurar encoding para Windows
    if sys.platform == 'win32':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    
    print(f"{Colors.BLUE}{'='*60}")
    print("VALIDACION DE VARIABLES DE ENTORNO")
    print(f"{'='*60}{Colors.RESET}\n")
    
    # Verificar archivo .env
    exists, messages = check_env_file()
    for msg in messages:
        print(msg)
    
    if not exists:
        print(f"\n{Colors.RED}[ERROR] No se puede continuar sin el archivo .env{Colors.RESET}")
        print(f"{Colors.YELLOW}[INFO] Crea un archivo .env en el directorio raiz del proyecto{Colors.RESET}")
        return 1
    
    # Cargar variables
    env_vars = load_env_file()
    print(f"\n📋 Variables encontradas en .env: {len(env_vars)}\n")
    
    # Verificar variables
    errors, warnings, info = check_variables(env_vars)
    
    # Mostrar resultados
    if errors:
        print(f"{Colors.RED}[ERRORES CRITICOS] ({len(errors)}):{Colors.RESET}")
        for error in errors:
            print(f"  {error}")
        print()
    
    if warnings:
        print(f"{Colors.YELLOW}[ADVERTENCIAS] ({len(warnings)}):{Colors.RESET}")
        for warning in warnings:
            print(f"  {warning}")
        print()
    
    if info:
        print(f"{Colors.GREEN}[CONFIGURADO CORRECTAMENTE] ({len(info)}):{Colors.RESET}")
        for item in info:
            print(f"  {item}")
        print()
    
    # Resumen
    print(f"{Colors.BLUE}{'='*60}{Colors.RESET}")
    if errors:
        print(f"{Colors.RED}[X] NO LISTO PARA PRODUCCION - Corrige los errores criticos{Colors.RESET}")
        return 1
    elif warnings:
        print(f"{Colors.YELLOW}[!] CASI LISTO - Revisa las advertencias antes de desplegar{Colors.RESET}")
        return 0
    else:
        print(f"{Colors.GREEN}[OK] LISTO PARA PRODUCCION{Colors.RESET}")
        return 0

if __name__ == '__main__':
    exit(main())

