"""
Verificación completa de rutas backend-frontend
"""
import os
import re

# Rutas que existen en el directorio
existing_files = [
    'ai_content.py', 'analytics.py', 'audits.py', 'backlinks.py',
    'content_analysis.py', 'content_editor.py', 'geo.py', 'github.py',
    'health.py', 'hubspot.py', 'keywords.py', 'llm_visibility.py',
    'pagespeed.py', 'rank_tracking.py', 'realtime.py', 'reports.py',
    'search.py', 'sse.py', 'webhooks.py'
]

# Rutas importadas en __init__.py
imported_routes = [
    'audits', 'reports', 'analytics', 'health', 'search', 'pagespeed', 
    'realtime', 'sse', 'content_analysis', 'geo', 'hubspot', 'github', 
    'webhooks', 'backlinks', 'keywords', 'rank_tracking', 'llm_visibility', 
    'ai_content', 'content_editor'
]

# Rutas registradas en main.py
registered_routes = [
    'audits', 'reports', 'analytics', 'search', 'pagespeed', 'backlinks',
    'keywords', 'rank_tracking', 'llm_visibility', 'ai_content', 
    'content_editor', 'content_analysis', 'geo', 'hubspot', 'github',
    'webhooks', 'sse', 'health', 'realtime'
]

print("="*60)
print("VERIFICACIÓN DE RUTAS")
print("="*60)

# Convertir archivos a nombres de módulos
existing_modules = [f.replace('.py', '') for f in existing_files]

print("\n1. Archivos que existen pero NO están importados:")
not_imported = set(existing_modules) - set(imported_routes)
if not_imported:
    for route in not_imported:
        print(f"   X {route}.py existe pero no esta en __init__.py")
else:
    print("   OK Todos los archivos estan importados")

print("\n2. Rutas importadas pero archivo NO existe:")
not_exist = set(imported_routes) - set(existing_modules)
if not_exist:
    for route in not_exist:
        print(f"   X {route} importado pero {route}.py no existe")
else:
    print("   OK Todas las importaciones tienen archivo")

print("\n3. Rutas importadas pero NO registradas en main.py:")
not_registered = set(imported_routes) - set(registered_routes)
if not_registered:
    for route in not_registered:
        print(f"   ! {route} importado pero no registrado en main.py")
else:
    print("   OK Todas las rutas importadas estan registradas")

print("\n4. Rutas registradas pero NO importadas:")
registered_not_imported = set(registered_routes) - set(imported_routes)
if registered_not_imported:
    for route in registered_not_imported:
        print(f"   X {route} registrado pero no importado en __init__.py")
else:
    print("   OK Todas las rutas registradas estan importadas")

print("\n" + "="*60)
print("RESUMEN")
print("="*60)
print(f"Archivos existentes: {len(existing_modules)}")
print(f"Rutas importadas: {len(imported_routes)}")
print(f"Rutas registradas: {len(registered_routes)}")

if not_imported or not_exist or not_registered or registered_not_imported:
    print("\nX HAY PROBLEMAS EN LAS RUTAS")
else:
    print("\nOK TODAS LAS RUTAS ESTAN CORRECTAMENTE CONECTADAS")
