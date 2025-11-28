import requests
import json
import time

# Configuración
API_URL = "http://localhost:8000/api"
# Reemplaza con tus IDs reales después de conectar
CONNECTION_ID = "tu_connection_id" 
REPO_ID = "tu_repo_id"

def print_step(step):
    print(f"\n{'='*50}")
    print(f"🚀 PASO: {step}")
    print(f"{'='*50}")

def test_audit_blogs_geo():
    print_step("Auditando Blogs con GEO (Generative Engine Optimization)")
    url = f"{API_URL}/github/audit-blogs-geo/{CONNECTION_ID}/{REPO_ID}"
    
    try:
        response = requests.post(url)
        if response.status_code == 200:
            data = response.json()
            print("✅ Auditoría Exitosa!")
            
            # Debug: Mostrar estructura básica
            print(f"Status: {data.get('status')}")
            
            if data.get('status') == 'no_blogs_found':
                print("⚠️ No se encontraron blogs/páginas en este repositorio.")
                print(f"Mensaje: {data.get('message')}")
                return []
            
            summary = data.get('summary', {})
            print(f"📊 Archivos analizados: {summary.get('total_blogs', 0)}")
            print(f"⚠️ Archivos con issues: {summary.get('blogs_with_issues', 0)}")
            
            blogs = data.get('blogs', [])
            if blogs:
                print(f"\n📝 Archivos encontrados ({len(blogs)}):")
                for b in blogs[:3]:
                    print(f"   - {b.get('file_path')} (Score: {b.get('geo_score', 'N/A')})") 
                
                # Retornar paths encontrados para el siguiente paso
                paths = [b.get('file_path') for b in blogs]
                print(f"\n🔍 DEBUG: Retornando {len(paths)} paths")
                return paths
            
            print("\n🔍 DEBUG: No hay blogs en la respuesta, retornando lista vacía")
            return []
        else:
            print(f"❌ Error: {response.status_code}")
            print(response.text)
            return []
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        return []

def test_create_geo_pr(blog_paths):
    if not blog_paths:
        print("⚠️ No hay archivos para crear PR. Saltando paso.")
        return

    print_step(f"Creando PR con Fixes GEO para {len(blog_paths)} archivos")
    url = f"{API_URL}/github/create-geo-fixes-pr/{CONNECTION_ID}/{REPO_ID}"
    
    # Usar los paths reales encontrados
    payload = {
        "blog_paths": blog_paths,
        "include_geo": True
    }
    
    print(f"Enviando payload para: {blog_paths}")
    
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            data = response.json()
            print("✅ PR Creado Exitosamente!")
            print(f"🔗 URL del PR: {data.get('pr', {}).get('html_url')}")
            print(f"🛠️ Fixes aplicados: {data.get('fixes_applied')}")
            print(f"🤖 GEO Fixes: {data.get('geo_fixes')}")
        else:
            print(f"❌ Error: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"❌ Error de conexión: {e}")

def get_user_input():
    print("\n🔍 Configuración Inicial")
    conn_id = input("👉 Ingresa tu CONNECTION_ID (o presiona Enter si ya lo pusiste en el código): ").strip()
    if conn_id:
        global CONNECTION_ID
        CONNECTION_ID = conn_id
    
    repo_id = input("👉 Ingresa tu REPO_ID (o presiona Enter si ya lo pusiste en el código): ").strip()
    if repo_id:
        global REPO_ID
        REPO_ID = repo_id

if __name__ == "__main__":
    print("🚀 Iniciando prueba de GEO Auditor...")
    
    # 1. Configuración
    # 1. Configuración
    # if CONNECTION_ID == "tu_connection_id" or REPO_ID == "tu_repo_id":
    #    get_user_input()
    
    CONNECTION_ID = "950f7afc-fa8d-4baf-9bef-cd00c780f05c"
    REPO_ID = "dec8ccd2-5934-47b3-bc49-8e12ff70fde2"
    
    if CONNECTION_ID == "tu_connection_id" or REPO_ID == "tu_repo_id":
        print("\n❌ Error: Necesitas configurar CONNECTION_ID y REPO_ID.")
        print("💡 Tip: Ve a http://localhost:8000/api/github/auth-url para conectar GitHub y obtener el ID.")
        exit(1)

    # 2. Ejecutar pruebas
    print(f"\n✅ Usando Connection: {CONNECTION_ID}, Repo: {REPO_ID}")
    
    # Prueba 1: Auditoría
    found_paths = test_audit_blogs_geo()
    
    # Prueba 2: Crear PR (forzar con fixes demo si es necesario)
    if found_paths:
        run_pr = input("\n¿Quieres crear el PR con fixes ahora? (s/n): ").lower()
        if run_pr == 's':
            # Si no hay issues, generar fixes demo para probar el flujo
            print("\n💡 Generando fixes de demostración para validar el flujo completo...")
            test_create_geo_pr(found_paths)
        else:
            print("👋 Prueba finalizada sin crear PR.")
    else:
        print("\n⚠️ No se encontraron archivos para auditar. Revisa que el repositorio sea Next.js, Gatsby, Hugo, etc.")
