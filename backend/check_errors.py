"""Verificación final de errores potenciales"""
import sys
import os

errors = []

print("="*60)
print("VERIFICACION FINAL DE ERRORES")
print("="*60)

# 1. Sintaxis
print("\n1. Verificando sintaxis...")
try:
    import py_compile
    for root, dirs, files in os.walk('app'):
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                try:
                    py_compile.compile(filepath, doraise=True)
                except py_compile.PyCompileError as e:
                    errors.append(f"Sintaxis: {filepath} - {e}")
    print("   OK Sintaxis correcta")
except Exception as e:
    errors.append(f"Error verificando sintaxis: {e}")

# 2. Imports circulares
print("\n2. Verificando imports circulares...")
circular_imports = []
try:
    # Verificar audit_service
    with open('app/services/audit_service.py', 'r') as f:
        content = f.read()
        if 'from .audit_service import' in content:
            circular_imports.append('audit_service.py importa de si mismo')
    
    if circular_imports:
        for ci in circular_imports:
            errors.append(f"Import circular: {ci}")
    else:
        print("   OK Sin imports circulares")
except Exception as e:
    errors.append(f"Error verificando imports: {e}")

# 3. Strings mal escapados
print("\n3. Verificando strings...")
try:
    with open('app/api/routes/sse.py', 'r') as f:
        lines = f.readlines()
        for i, line in enumerate(lines, 1):
            if 'yield f"' in line and '\\n\\n' not in line and '\n\n' in line:
                errors.append(f"sse.py:{i} - String mal escapado")
    print("   OK Strings correctos")
except Exception as e:
    errors.append(f"Error verificando strings: {e}")

# 4. Archivos movidos
print("\n4. Verificando archivos en ubicacion correcta...")
wrong_location = []
services_in_routes = ['code_fixer_service.py', 'github_service.py', 'path_mapper_service.py']
for service in services_in_routes:
    if os.path.exists(f'app/api/routes/{service}'):
        wrong_location.append(f'{service} debe estar en app/services/')

if wrong_location:
    for wl in wrong_location:
        errors.append(f"Ubicacion incorrecta: {wl}")
else:
    print("   OK Archivos en ubicacion correcta")

# 5. Rutas registradas
print("\n5. Verificando rutas registradas...")
try:
    with open('app/main.py', 'r') as f:
        main_content = f.read()
        if 'sse.router' not in main_content:
            errors.append("SSE no registrado en main.py")
        else:
            print("   OK SSE registrado")
except Exception as e:
    errors.append(f"Error verificando rutas: {e}")

# Resumen
print("\n" + "="*60)
print("RESUMEN")
print("="*60)

if errors:
    print(f"\nX ENCONTRADOS {len(errors)} ERRORES:\n")
    for error in errors:
        print(f"  - {error}")
    sys.exit(1)
else:
    print("\nOK SISTEMA SIN ERRORES")
    print("\nProximo paso:")
    print("  docker-compose restart backend")
    sys.exit(0)
