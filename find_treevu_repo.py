"""
Script para listar repositorios y obtener IDs
"""
import requests
import sys

BASE_URL = "http://localhost:8000/api/github"

def listar_repos(connection_id):
    """Lista todos los repositorios sincronizados"""
    
    print(f"🔍 Buscando repositorios para connection: {connection_id}\n")
    
    # 1. Primero sincronizar repos
    print("📡 Sincronizando repositorios...")
    sync_url = f"{BASE_URL}/sync/{connection_id}"
    
    try:
        response = requests.post(sync_url)
        if response.status_code == 200:
            repos = response.json()
            print(f"✅ Sincronizados {len(repos)} repositorios\n")
        else:
            print(f"⚠️  Error en sync: {response.status_code}")
            print(f"    {response.text}\n")
    except Exception as e:
        print(f"❌ Error: {e}\n")
    
    # 2. Listar todos los repos
    print("📋 Lista de repositorios disponibles:")
    print("=" * 80)
    
    list_url = f"{BASE_URL}/repos/{connection_id}"
    
    try:
        response = requests.get(list_url)
        if response.status_code == 200:
            repos = response.json()
            
            # Buscar TreevuLadingPageM
            treevu_repo = None
            
            for idx, repo in enumerate(repos, 1):
                is_treevu = "treevu" in repo['name'].lower() or "TreevuLadingPageM" in repo['name']
                marker = "👉 " if is_treevu else "   "
                
                print(f"{marker}{idx}. {repo['full_name']}")
                print(f"   ID: {repo['id']}")
                print(f"   Site Type: {repo.get('site_type', 'unknown')}")
                print(f"   URL: {repo['url']}")
                
                if is_treevu:
                    treevu_repo = repo
                
                print()
            
            # Si encontramos TreevuLadingPageM
            if treevu_repo:
                print("=" * 80)
                print("✅ ¡Repositorio TreevuLadingPageM encontrado!")
                print("=" * 80)
                print(f"📛 Nombre: {treevu_repo['full_name']}")
                print(f"🔑 REPO_ID: {treevu_repo['id']}")
                print(f"🏗️  Site Type: {treevu_repo.get('site_type', 'unknown')}")
                print(f"🌐 URL: {treevu_repo['url']}")
                print()
                print("💡 Usa este REPO_ID para ejecutar test_geo_flow.py")
                print()
                return treevu_repo['id']
            else:
                print("⚠️  No se encontró TreevuLadingPageM en la lista")
                print("   Verifica que el repo esté en tu cuenta de GitHub")
                
        else:
            print(f"❌ Error: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"❌ Error: {e}")
    
    return None


if __name__ == "__main__":
    # Tu CONNECTION_ID (el mismo de antes)
    CONNECTION_ID = "950f7afc-fa8d-4baf-9bef-cd00c780f05c"
    
    print("🚀 Script de Búsqueda de Repositorios\n")
    
    repo_id = listar_repos(CONNECTION_ID)
    
    if repo_id:
        print(f"\n✅ LISTO! Copia este REPO_ID: {repo_id}")
    else:
        print("\n❌ No se pudo encontrar el repositorio")
        print("   Asegúrate de que:")
        print("   1. El repo existe en tu GitHub")
        print("   2. La GitHub App tiene acceso a él")
        print("   3. El nombre contiene 'Treevu' o 'TreevuLadingPageM'")
