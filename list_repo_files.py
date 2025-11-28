"""
Lista todos los archivos del repositorio para debug
"""
import requests

CONNECTION_ID = "950f7afc-fa8d-4baf-9bef-cd00c780f05c"
REPO_FULL_NAME = "nicolasleiva/crawler_ai"
API_URL = "http://localhost:8000/api"

def list_files():
    print(f"📂 Listando archivos en {REPO_FULL_NAME}...\n")
    
    # Primero obtenemos el token del connection
    url = f"{API_URL}/github/connections"
    response = requests.get(url)
    
    if response.status_code != 200:
        print(f"Error obteniendo conexiones: {response.status_code}")
        return
    
    # Ahora vamos directo a GitHub API
    # Usamos la API pública de GitHub (no requiere autenticación para repos públicos)
    github_api_url = f"https://api.github.com/repos/{REPO_FULL_NAME}/git/trees/main?recursive=1"
    
    print(f"🔍 Consultando: {github_api_url}\n")
    gh_response = requests.get(github_api_url)
    
    if gh_response.status_code != 200:
        print(f"Error: {gh_response.status_code}")
        print(gh_response.text)
        return
    
    data = gh_response.json()
    tree = data.get("tree", [])
    
    print(f"📊 Total de archivos/carpetas: {len(tree)}\n")
    
    # Filtrar solo archivos importantes (tsx, jsx, ts, js, mdx, md)
    important_files = [
        item for item in tree 
        if item["type"] == "blob" and any(item["path"].endswith(ext) for ext in [
            ".tsx", ".jsx", ".ts", ".js", ".mdx", ".md", "package.json"
        ])
    ]
    
    print(f"📄 Archivos relevantes ({len(important_files)}):\n")
    for item in important_files[:30]:  # Primeros 30
        print(f"   {item['path']}")
    
    if len(important_files) > 30:
        print(f"\n   ... y {len(important_files) - 30} más")
    
    # Buscar específicamente los patrones que el auditor busca
    print("\n\n🔎 Buscando patrones específicos:\n")
    
    app_pages = [f for f in tree if "app/" in f["path"] and f["path"].endswith(("page.tsx", "page.jsx"))]
    print(f"   app/**/page.tsx: {len(app_pages)} encontrados")
    for p in app_pages[:5]:
        print(f"      - {p['path']}")
    
    pages_tsx = [f for f in tree if "pages/" in f["path"] and f["path"].endswith((".tsx", ".jsx"))]
    print(f"\n   pages/**/*.tsx: {len(pages_tsx)} encontrados")
    for p in pages_tsx[:5]:
        print(f"      - {p['path']}")
    
    src_pages = [f for f in tree if "src/" in f["path"] and f["path"].endswith((".tsx", ".jsx", ".ts", ".js"))]
    print(f"\n   src/**/*: {len(src_pages)} encontrados")
    for p in src_pages[:5]:
        print(f"      - {p['path']}")

if __name__ == "__main__":
    list_files()
