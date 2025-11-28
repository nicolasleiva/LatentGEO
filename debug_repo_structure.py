import requests
import json

# Configuración
CONNECTION_ID = "950f7afc-fa8d-4baf-9bef-cd00c780f05c"
REPO_ID = "8620328b-afb5-4de3-8577-636164111e4d"
API_URL = "http://localhost:8000/api"

def debug_repo():
    print(f"🔍 Analizando estructura de repo {REPO_ID}...")
    
    # Usar endpoint de análisis que ya existe
    url = f"{API_URL}/github/analyze/{CONNECTION_ID}/{REPO_ID}"
    
    try:
        response = requests.post(url)
        print(f"Status: {response.status_code}")
        print(json.dumps(response.json(), indent=2))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_repo()
