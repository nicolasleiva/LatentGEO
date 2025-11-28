from app.core.database import SessionLocal
from app.models.github import GitHubConnection
from github import Github

def inspect_repo():
    db = SessionLocal()
    conn = db.query(GitHubConnection).filter(GitHubConnection.id == '950f7afc-fa8d-4baf-9bef-cd00c780f05c').first()
    
    if not conn:
        print("No connection found")
        return

    # Desencriptar token (si está encriptado)
    # Asumimos que la clase GitHubOAuth maneja esto, pero aquí lo haremos manual si es necesario
    # O mejor, usamos la librería github directamente con el token (si no está encriptado en la BD, que debería estarlo)
    
    # Para simplificar, voy a imprimir la estructura usando el cliente de la app
    from app.integrations.github.client import GitHubClient
    
    client = GitHubClient(conn.access_token) # El cliente maneja la desencriptación si se le pasa el objeto, pero aquí le paso el token raw?
    # No, el cliente espera el token desencriptado.
    
    # Vamos a desencriptarlo
    from app.integrations.github.oauth import GitHubOAuth
    token = GitHubOAuth.decrypt_token(conn.access_token)
    
    g = Github(token)
    repo = g.get_repo("nicolasleiva/lalanding")
    
    print(f"Repo: {repo.full_name}")
    print("Files in root:")
    for content in repo.get_contents(""):
        print(f" - {content.path} ({content.type})")
        
    print("\nFiles in src:")
    try:
        for content in repo.get_contents("src"):
            print(f" - {content.path} ({content.type})")
    except:
        print("No src folder")

    print("\nFiles in src/pages:")
    try:
        for content in repo.get_contents("src/pages"):
            print(f" - {content.path} ({content.type})")
    except:
        print("No src/pages folder")

if __name__ == "__main__":
    inspect_repo()
