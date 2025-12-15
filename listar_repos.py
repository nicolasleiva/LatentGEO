import requests

CONNECTION_ID = "950f7afc-fa8d-4baf-9bef-cd00c780f05c"
BASE_URL = "http://localhost:8000/api/github"

print("🔄 Sincronizando repositorios...")
try:
    resp = requests.post(f"{BASE_URL}/sync/{CONNECTION_ID}")
    if resp.status_code == 200:
        print(f"✅ Sincronizados: {len(resp.json())} repos\n")
    else:
        print(f"❌ Error sync: {resp.status_code} - {resp.text}\n")
except Exception as e:
    print(f"❌ Error conexión: {e}\n")

print("📋 Listando repositorios...")
try:
    repos = requests.get(f"{BASE_URL}/repos/{CONNECTION_ID}").json()
    print(f"\n📊 Total: {len(repos)} repos\n")
    
    # Ordenar por nombre
    repos.sort(key=lambda x: x['name'].lower())
    
    for i, r in enumerate(repos, 1):
        marker = "👉 " if "test_landing" in r['name'] else "   "
        print(f"{marker}{i}. {r['name']}")
        print(f"      ID: {r['id']}")
        print(f"      URL: {r['url']}")
        print()

except Exception as e:
    print(f"❌ Error listado: {e}")
