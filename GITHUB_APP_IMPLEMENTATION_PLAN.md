# 🚀 GitHub App - Plan de Implementación Profesional

## 📋 Resumen Ejecutivo

GitHub App que audita automáticamente sitios web en repositorios y crea Pull Requests con fixes SEO/GEO optimizados por IA.

**Diferenciador clave**: El único bot que entiende GEO (Generative Engine Optimization) además de SEO tradicional.

---

## 🎯 User Story Principal

```
Como desarrollador/equipo,
Quiero que mi sitio sea auditado automáticamente,
Para recibir PRs con fixes SEO/GEO listos para mergear,
Sin tener que ejecutar auditorías manualmente.
```

**Flujo completo:**
```
1. Usuario instala GitHub App en su repo
2. App detecta sitio web (Next.js, Gatsby, Hugo, HTML estático, etc.)
3. Ejecuta auditoría completa (SEO + GEO)
4. Genera fix plan con cambios específicos
5. Crea PR con:
   - Archivos modificados
   - Diff detallado
   - Reporte de mejoras esperadas
   - Link al dashboard completo
6. Usuario revisa, aprueba y mergea
7. (Opcional) Re-auditoría post-merge para validar mejoras
```

---

## 🏗️ Arquitectura Completa

### Backend (FastAPI)

```
backend/
├── app/
│   ├── integrations/
│   │   └── github/
│   │       ├── __init__.py
│   │       ├── oauth.py              # OAuth flow con GitHub
│   │       ├── client.py             # GitHub API client (PyGithub wrapper)
│   │       ├── repository_analyzer.py # Detecta tipo de sitio y estructura
│   │       ├── code_modifier.py      # Aplica fixes a archivos
│   │       ├── pr_generator.py       # Crea PRs profesionales
│   │       └── webhook_handler.py    # Maneja eventos de GitHub
│   │
│   ├── models/
│   │   └── github.py
│   │       ├── GitHubConnection      # OAuth tokens + config
│   │       ├── GitHubRepository      # Repos conectados
│   │       ├── GitHubPullRequest     # PRs creados
│   │       └── GitHubWebhookEvent    # Log de eventos
│   │
│   ├── api/routes/
│   │   └── github.py
│   │       ├── /github/auth-url      # Inicia OAuth
│   │       ├── /github/callback      # OAuth callback
│   │       ├── /github/repos         # Lista repos del usuario
│   │       ├── /github/install       # Instala app en un repo
│   │       ├── /github/audit/{repo}  # Audita un repo
│   │       ├── /github/create-pr     # Crea PR con fixes
│   │       └── /github/webhook       # Recibe eventos
│   │
│   └── services/
│       └── github_service.py
│           ├── sync_repositories()
│           ├── analyze_repository()
│           ├── apply_fixes_to_code()
│           └── create_pull_request()
```

### Frontend (Next.js)

```
frontend/
├── app/
│   └── integrations/
│       └── github/
│           ├── connect/page.tsx       # Conectar GitHub
│           ├── callback/page.tsx      # OAuth callback
│           ├── repos/page.tsx         # Lista de repos
│           ├── [repo]/
│           │   ├── page.tsx           # Detalles del repo
│           │   └── prs/page.tsx       # PRs generados
│           └── settings/page.tsx      # Configuración
```

---

## 📊 Modelos de Base de Datos

### GitHubConnection
```python
class GitHubConnection(Base):
    id: UUID
    user_id: UUID (futuro)
    
    # OAuth
    github_user_id: str           # ID del usuario en GitHub
    github_username: str
    access_token: str             # Encrypted
    token_type: str               # "bearer"
    scope: str                    # Permisos otorgados
    expires_at: datetime          # Si es temporal
    
    # Metadata
    installation_id: str          # ID de instalación de la app
    account_type: str             # "user" o "organization"
    is_active: bool
    
    created_at: datetime
    updated_at: datetime
    
    # Relaciones
    repositories: List[GitHubRepository]
```

### GitHubRepository
```python
class GitHubRepository(Base):
    id: UUID
    connection_id: UUID
    
    # Datos del repo
    github_repo_id: str           # ID interno de GitHub
    full_name: str                # "owner/repo"
    name: str
    owner: str
    url: str
    homepage_url: str             # URL del sitio desplegado
    
    # Detección automática
    site_type: str                # "nextjs", "gatsby", "hugo", "html", etc.
    base_path: str                # Ruta donde está el sitio
    build_command: str            # npm run build, gatsby build, etc.
    output_dir: str               # .next, public, dist, etc.
    
    # Config de auditoría
    auto_audit: bool              # Auditar en cada push
    auto_pr: bool                 # Crear PR automáticamente
    branch_name_pattern: str      # "seo-fix-{date}"
    
    # Estado
    last_audited_at: datetime
    last_commit_sha: str
    is_active: bool
    
    created_at: datetime
    updated_at: datetime
    
    # Relaciones
    pull_requests: List[GitHubPullRequest]
```

### GitHubPullRequest
```python
class GitHubPullRequest(Base):
    id: UUID
    repository_id: UUID
    audit_id: int                 # Link a la auditoría que generó esto
    
    # Datos del PR
    github_pr_id: str
    pr_number: int
    title: str
    body: str                     # Markdown con detalles
    branch_name: str
    base_branch: str              # main, master, develop
    
    # Archivos modificados
    files_changed: int
    additions: int
    deletions: int
    modified_files: JSON          # Lista de archivos con paths
    
    # Estado
    status: str                   # "pending", "open", "merged", "closed"
    html_url: str                 # URL del PR en GitHub
    merged_at: datetime
    closed_at: datetime
    
    # Métricas esperadas
    expected_improvements: JSON   # Score antes/después
    
    created_at: datetime
    updated_at: datetime
```

### GitHubWebhookEvent
```python
class GitHubWebhookEvent(Base):
    id: UUID
    repository_id: UUID
    
    event_type: str               # "push", "pull_request", "installation"
    event_id: str                 # De GitHub
    payload: JSON
    
    processed: bool
    processed_at: datetime
    error_message: str
    
    created_at: datetime
```

---

## 🔐 GitHub OAuth Flow

### Configuración en GitHub

1. **Crear GitHub App** en https://github.com/settings/apps/new

**Permisos necesarios:**
- Repository permissions:
  - Contents: Read & Write (para crear commits)
  - Pull requests: Read & Write
  - Metadata: Read
  - Webhooks: Read & Write
- Organization permissions:
  - Members: Read (para equipos)

**Webhook URL**: `https://tu-dominio.com/api/github/webhook`

**OAuth Redirect URL**: `https://tu-dominio.com/integrations/github/callback`

### 2. OAuth Implementation

```python
# app/integrations/github/oauth.py

GITHUB_CLIENT_ID = settings.GITHUB_CLIENT_ID
GITHUB_CLIENT_SECRET = settings.GITHUB_CLIENT_SECRET
REDIRECT_URI = settings.GITHUB_REDIRECT_URI

SCOPES = ["repo", "read:org", "write:discussion"]

def get_authorization_url() -> str:
    return (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={GITHUB_CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&scope={' '.join(SCOPES)}"
        f"&state={generate_state_token()}"
    )

async def exchange_code(code: str) -> Dict:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": REDIRECT_URI
            },
            headers={"Accept": "application/json"}
        )
        return response.json()

async def get_user_info(access_token: str) -> Dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json"
            }
        )
        return response.json()
```

---

## 🤖 GitHub API Client

```python
# app/integrations/github/client.py

from github import Github, GithubException
from typing import List, Dict, Optional

class GitHubClient:
    """Cliente profesional para GitHub API usando PyGithub"""
    
    def __init__(self, access_token: str):
        self.gh = Github(access_token)
        self.access_token = access_token
    
    async def get_user_repos(self) -> List[Dict]:
        """Obtiene repositorios del usuario con filtros relevantes"""
        repos = []
        for repo in self.gh.get_user().get_repos():
            # Filtrar solo repos que probablemente contengan un sitio web
            if self._is_potential_website_repo(repo):
                repos.append({
                    "github_repo_id": str(repo.id),
                    "full_name": repo.full_name,
                    "name": repo.name,
                    "owner": repo.owner.login,
                    "url": repo.html_url,
                    "homepage_url": repo.homepage or "",
                    "default_branch": repo.default_branch,
                    "private": repo.private
                })
        return repos
    
    def _is_potential_website_repo(self, repo) -> bool:
        """Detecta si el repo probablemente contenga un sitio web"""
        # Buscar archivos comunes de sitios web
        try:
            contents = repo.get_contents("")
            filenames = [c.name.lower() for c in contents]
            
            # Next.js
            if "next.config.js" in filenames or "next.config.mjs" in filenames:
                return True
            # Gatsby
            if "gatsby-config.js" in filenames:
                return True
            # Hugo
            if "config.toml" in filenames or "config.yaml" in filenames:
                return True
            # HTML estático
            if "index.html" in filenames:
                return True
            # Astro
            if "astro.config.mjs" in filenames:
                return True
            
            return False
        except:
            return False
    
    async def detect_site_type(self, repo_full_name: str) -> Dict:
        """Detecta el tipo de sitio y su configuración"""
        repo = self.gh.get_repo(repo_full_name)
        contents = repo.get_contents("")
        
        # Análisis de configuración
        config = {
            "site_type": "unknown",
            "base_path": "/",
            "build_command": None,
            "output_dir": None
        }
        
        for content in contents:
            if content.name == "package.json":
                # Analizar package.json para detectar framework
                pkg = json.loads(content.decoded_content)
                
                if "next" in pkg.get("dependencies", {}):
                    config["site_type"] = "nextjs"
                    config["build_command"] = "npm run build"
                    config["output_dir"] = ".next"
                elif "gatsby" in pkg.get("dependencies", {}):
                    config["site_type"] = "gatsby"
                    config["build_command"] = "gatsby build"
                    config["output_dir"] = "public"
                # ... más frameworks
        
        return config
    
    async def create_branch(self, repo_full_name: str, branch_name: str, base_branch: str = "main"):
        """Crea una nueva branch"""
        repo = self.gh.get_repo(repo_full_name)
        base = repo.get_branch(base_branch)
        repo.create_git_ref(f"refs/heads/{branch_name}", base.commit.sha)
    
    async def update_file(self, repo_full_name: str, file_path: str, 
                         content: str, branch: str, commit_message: str):
        """Actualiza un archivo en el repositorio"""
        repo = self.gh.get_repo(repo_full_name)
        
        try:
            # Obtener archivo existente
            file = repo.get_contents(file_path, ref=branch)
            repo.update_file(
                path=file_path,
                message=commit_message,
                content=content,
                sha=file.sha,
                branch=branch
            )
        except:
            # Archivo no existe, crearlo
            repo.create_file(
                path=file_path,
                message=commit_message,
                content=content,
                branch=branch
            )
    
    async def create_pull_request(self, repo_full_name: str, title: str, 
                                  body: str, head_branch: str, base_branch: str = "main"):
        """Crea un Pull Request"""
        repo = self.gh.get_repo(repo_full_name)
        pr = repo.create_pull(
            title=title,
            body=body,
            head=head_branch,
            base=base_branch
        )
        return {
            "github_pr_id": str(pr.id),
            "pr_number": pr.number,
            "html_url": pr.html_url
        }
```

---

## 🔧 Repository Analyzer

```python
# app/integrations/github/repository_analyzer.py

class RepositoryAnalyzer:
    """Analiza repositorios para determinar estructura y archivos a modificar"""
    
    def __init__(self, github_client: GitHubClient):
        self.client = github_client
    
    async def find_html_files(self, repo_full_name: str, site_type: str) -> List[str]:
        """Encuentra archivos HTML/JSX/TSX según el tipo de sitio"""
        
        if site_type == "nextjs":
            return await self._find_nextjs_pages(repo_full_name)
        elif site_type == "gatsby":
            return await self._find_gatsby_pages(repo_full_name)
        elif site_type == "html":
            return await self._find_html_files(repo_full_name)
        # ... más tipos
    
    async def _find_nextjs_pages(self, repo_full_name: str) -> List[str]:
        """Encuentra páginas de Next.js (app router y pages router)"""
        repo = self.client.gh.get_repo(repo_full_name)
        pages = []
        
        # App Router
        try:
            app_dir = repo.get_contents("app")
            pages.extend(self._scan_directory_for_pages(app_dir, "page.tsx"))
            pages.extend(self._scan_directory_for_pages(app_dir, "page.jsx"))
        except:
            pass
        
        # Pages Router
        try:
            pages_dir = repo.get_contents("pages")
            pages.extend(self._scan_directory_for_files(pages_dir, [".tsx", ".jsx"]))
        except:
            pass
        
        return pages
    
    def _scan_directory_for_pages(self, directory, filename: str) -> List[str]:
        """Escanea recursivamente buscando archivos específicos"""
        files = []
        for content in directory:
            if content.type == "dir":
                try:
                    subdir = self.client.gh.get_repo(repo_full_name).get_contents(content.path)
                    files.extend(self._scan_directory_for_pages(subdir, filename))
                except:
                    pass
            elif content.name == filename:
                files.append(content.path)
        return files
```

---

## 🛠️ Code Modifier Service

```python
# app/integrations/github/code_modifier.py

class CodeModifierService:
    """Aplica fixes SEO/GEO a archivos de código"""
    
    async def apply_fixes_to_html(self, html_content: str, fixes: List[Dict]) -> str:
        """Aplica fixes a HTML estático"""
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        for fix in fixes:
            if fix["type"] == "meta_description":
                self._update_meta_description(soup, fix["value"])
            elif fix["type"] == "title":
                self._update_title(soup, fix["value"])
            elif fix["type"] == "h1":
                self._update_h1(soup, fix["value"])
            # ... más tipos
        
        return str(soup)
    
    async def apply_fixes_to_nextjs(self, file_content: str, fixes: List[Dict]) -> str:
        """Aplica fixes a componentes Next.js/React"""
        # Usar AST parsing para modificar código TypeScript/JSX sin romper nada
        import libcst as cst
        
        # Parse código
        module = cst.parse_module(file_content)
        
        # Aplicar transformaciones
        transformer = NextJSTransformer(fixes)
        modified_tree = module.visit(transformer)
        
        return modified_tree.code
    
    def _update_meta_description(self, soup, value: str):
        """Actualiza o crea meta description"""
        meta = soup.find("meta", attrs={"name": "description"})
        if meta:
            meta["content"] = value
        else:
            head = soup.find("head")
            if head:
                new_meta = soup.new_tag("meta", attrs={"name": "description", "content": value})
                head.append(new_meta)
```

Continúo con el resto de la implementación...
