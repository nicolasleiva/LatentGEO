import requests

CONNECTION_ID = "950f7afc-fa8d-4baf-9bef-cd00c780f05c"
BASE_URL = "http://localhost:8000/api/github"

print("🔄 Sincronizando repositorios...")
resp = requests.post(f"{BASE_URL}/sync/{CONNECTION_ID}")

if resp.status_code == 200:
    print(f"✅ Sincronizados: {len(resp.json())} repos\n")
else:
    print(f"❌ Error: {resp.status_code} - {resp.text}\n")

print("📋 Listando todos los repositorios...")
repos = requests.get(f"{BASE_URL}/repos/{CONNECTION_ID}").json()

print(f"\n📊 Total de repositorios: {len(repos)}\n")

# Buscar TreevuLadingPageMain
treevu_repos = [r for r in repos if 'treevu' in r.get('name', '').lower()]

if treevu_repos:
    print(f"🎯 Repositorios con 'treevu' encontrados: {len(treevu_repos)}\n")
    for r in treevu_repos:
        print(f"  ✅ {r['full_name']}")
        print(f"     ID: {r['id']}")
        print(f"     Site Type: {r.get('site_type', 'None')}")
        print()
else:
    print("❌ No se encontró ningún repo con 'treevu' en el nombre\n")

print("\n📝 Primeros 20 repositorios:")
for i, r in enumerate(repos[:20], 1):
    print(f"  {i}. {r['name']}")
