"""
GitHub API Client - Professional wrapper around PyGithub
"""
import json
import base64
from typing import List, Dict, Optional, Any
from github import Github, GithubException, Repository, ContentFile
from ...core.logger import get_logger

logger = get_logger(__name__)


class GitHubClient:
    """Cliente profesional para GitHub API"""
    
    def __init__(self, access_token: str):
        """
        Inicializa el cliente de GitHub
        
        Args:
            access_token: Token de acceso OAuth
        """
        self.gh = Github(access_token, per_page=100)
        self.access_token = access_token
        self._user = None
    
    def get_authenticated_user(self) -> Dict:
        """Obtiene info del usuario autenticado"""
        if not self._user:
            user = self.gh.get_user()
            self._user = {
                "id": str(user.id),
                "login": user.login,
                "name": user.name or user.login,
                "email": user.email,
                "avatar_url": user.avatar_url,
                "type": user.type  # User or Organization
            }
        return self._user
    
    def get_user_repos(self, filter_websites: bool = True) -> List[Dict]:
        """
        Obtiene repositorios del usuario
        
        Args:
            filter_websites: Si True, solo devuelve repos que parezcan ser sitios web
            
        Returns:
            Lista de repositorios con metadata
        """
        repos = []
        user = self.gh.get_user()
        
        for repo in user.get_repos():
            # Skip forks y archived repos
            if repo.fork or repo.archived:
                continue
            
            # Si se requiere filtro, verificar si parece ser un sitio web
            if filter_websites and not self._is_website_repo(repo):
                continue
            
            repos.append(self._format_repo_data(repo))
        
        logger.info(f"Found {len(repos)} repositories")
        return repos
    
    def get_repo(self, full_name: str) -> Repository.Repository:
        """
        Obtiene un repositorio específico
        
        Args:
            full_name: Nombre completo del repo (owner/name)
            
        Returns:
            Objeto Repository de PyGithub
        """
        return self.gh.get_repo(full_name)
    
    def detect_site_type(self, repo: Repository.Repository) -> Dict[str, Any]:
        """
        Detecta el tipo de sitio y su configuración
        
        Args:
            repo: Objeto Repository
            
        Returns:
            Dict con tipo de sitio y configuración
        """
        config = {
            "site_type": "unknown",
            "base_path": "/",
            "build_command": None,
            "output_dir": None,
            "framework_version": None
        }
        
        try:
            contents = repo.get_contents("")
            file_names = {c.name.lower(): c for c in contents if c.type == "file"}
            
            # 1. Frameworks modernos (Next.js, Gatsby, Astro, etc)
            if "package.json" in file_names:
                pkg_content = base64.b64decode(file_names["package.json"].content).decode('utf-8')
                pkg = json.loads(pkg_content)
                
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                
                if "next" in deps:
                    config["site_type"] = "nextjs"
                    config["build_command"] = "npm run build"
                    config["output_dir"] = ".next"
                    config["framework_version"] = deps["next"]
                    try:
                        repo.get_contents("app")
                        config["router_type"] = "app"
                    except:
                        config["router_type"] = "pages"
                
                elif "gatsby" in deps:
                    config["site_type"] = "gatsby"
                    config["build_command"] = "gatsby build"
                    config["output_dir"] = "public"
                    config["framework_version"] = deps["gatsby"]
                
                elif "astro" in deps:
                    config["site_type"] = "astro"
                    config["build_command"] = "npm run build"
                    config["output_dir"] = "dist"
                    config["framework_version"] = deps["astro"]
                
                elif "vite" in deps:
                    config["site_type"] = "vite"
                    config["build_command"] = "npm run build"
                    config["output_dir"] = "dist"
                    config["framework_version"] = deps["vite"]
                
                elif "react-scripts" in deps:
                    config["site_type"] = "create-react-app"
                    config["build_command"] = "npm run build"
                    config["output_dir"] = "build"
                    config["framework_version"] = deps.get("react", "")
                
                elif "@11ty/eleventy" in deps:
                    config["site_type"] = "11ty"
                    config["build_command"] = "npx eleventy"
                    config["output_dir"] = "_site"
            
            # 2. Generadores estáticos clásicos
            if config["site_type"] == "unknown":
                if any(f in file_names for f in ["config.toml", "config.yaml", "config.yml"]):
                    config["site_type"] = "hugo"
                    config["build_command"] = "hugo"
                    config["output_dir"] = "public"
                
                elif "_config.yml" in file_names:
                    config["site_type"] = "jekyll"
                    config["build_command"] = "jekyll build"
                    config["output_dir"] = "_site"
                
                # Detección por archivos de configuración
                elif any(f in file_names for f in ["vite.config.js", "vite.config.ts"]):
                    config["site_type"] = "vite"
                    config["build_command"] = "npm run build"
                    config["output_dir"] = "dist"
                
                elif "index.html" in file_names:
                    config["site_type"] = "html"
                    config["base_path"] = "/"
                
        except Exception as e:
            logger.error(f"Error detecting site type for {repo.full_name}: {e}")
        
        logger.info(f"Detected site type for {repo.full_name}: {config['site_type']}")
        return config
    
    def find_page_files(self, repo: Repository.Repository, site_type: str) -> List[str]:
        """
        Encuentra archivos de páginas según el tipo de sitio
        """
        files = []
        
        try:
            if site_type == "nextjs":
                try:
                    files.extend(self._scan_for_nextjs_pages(repo, "app"))
                except: pass
                try:
                    files.extend(self._scan_for_react_files(repo, "pages"))
                except: pass
            
            elif site_type == "gatsby":
                try:
                    files.extend(self._scan_for_react_files(repo, "src/pages"))
                except: pass
            
            elif site_type == "astro":
                try:
                    files.extend(self._scan_for_astro_files(repo, "src/pages"))
                except: pass
            
            elif site_type in ["vite", "create-react-app", "html", "unknown"]:
                # Para SPAs, index.html es crítico para SEO
                try:
                    if "index.html" in [c.name for c in repo.get_contents("")]:
                        files.append("index.html")
                except: pass
                
                # También buscar componentes
                try:
                    files.extend(self._scan_for_react_files(repo, ""))
                except: pass
                try:
                    files.extend(self._scan_for_react_files(repo, "src"))
                except: pass
            
        except Exception as e:
            logger.error(f"Error finding page files: {e}")
        
        logger.info(f"Found {len(files)} page files in {repo.full_name}")
        return files
    
    def create_branch(self, repo: Repository.Repository, branch_name: str, base_branch: str = None) -> str:
        """
        Crea una nueva branch
        
        Args:
            repo: Repository object
            branch_name: Nombre de la nueva branch
            base_branch: Branch base (default: default_branch del repo)
            
        Returns:
            SHA del commit base
        """
        if not base_branch:
            base_branch = repo.default_branch
        
        base = repo.get_branch(base_branch)
        repo.create_git_ref(f"refs/heads/{branch_name}", base.commit.sha)
        logger.info(f"Created branch {branch_name} in {repo.full_name}")
        return base.commit.sha
    
    def update_file(self, repo: Repository.Repository, file_path: str, 
                   content: str, branch: str, message: str) -> None:
        """
        Actualiza o crea un archivo
        
        Args:
            repo: Repository object
            file_path: Path del archivo
            content: Contenido nuevo
            branch: Branch donde hacer el commit
            message: Mensaje del commit
        """
        try:
            # Intentar obtener archivo existente
            file = repo.get_contents(file_path, ref=branch)
            repo.update_file(
                path=file_path,
                message=message,
                content=content,
                sha=file.sha,
                branch=branch
            )
            logger.info(f"Updated {file_path} in {repo.full_name}/{branch}")
        except GithubException as e:
            if e.status == 404:
                # Archivo no existe, crearlo
                repo.create_file(
                    path=file_path,
                    message=message,
                    content=content,
                    branch=branch
                )
                logger.info(f"Created {file_path} in {repo.full_name}/{branch}")
            else:
                raise
    
    def create_pull_request(self, repo: Repository.Repository, title: str,
                          body: str, head_branch: str, base_branch: str = None) -> Dict:
        """
        Crea un Pull Request
        
        Args:
            repo: Repository object
            title: Título del PR
            body: Descripción del PR (Markdown)
            head_branch: Branch con los cambios
            base_branch: Branch destino (default: default_branch)
            
        Returns:
            Dict con datos del PR
        """
        if not base_branch:
            base_branch = repo.default_branch
        
        pr = repo.create_pull(
            title=title,
            body=body,
            head=head_branch,
            base=base_branch
        )
        
        result = {
            "github_pr_id": str(pr.id),
            "pr_number": pr.number,
            "html_url": pr.html_url,
            "state": pr.state,
            "created_at": pr.created_at.isoformat()
        }
        
        logger.info(f"Created PR #{pr.number} in {repo.full_name}")
        return result
    
    # Helper methods
    
    def _is_website_repo(self, repo: Repository.Repository) -> bool:
        """Detecta si un repo probablemente contiene un sitio web"""
        try:
            contents = repo.get_contents("")
            file_names = [c.name.lower() for c in contents if c.type == "file"]
            
            # Buscar archivos indicativos de sitios web
            indicators = [
                "package.json", "next.config.js", "next.config.mjs",
                "gatsby-config.js", "config.toml", "config.yaml",
                "_config.yml", "index.html", "astro.config.mjs"
            ]
            
            return any(indicator in file_names for indicator in indicators)
        except:
            return False
    
    def _format_repo_data(self, repo: Repository.Repository) -> Dict:
        """Formatea datos del repositorio"""
        return {
            "github_repo_id": str(repo.id),
            "full_name": repo.full_name,
            "name": repo.name,
            "owner": repo.owner.login,
            "url": repo.html_url,
            "homepage_url": repo.homepage or "",
            "default_branch": repo.default_branch,
            "is_private": repo.private,
            "description": repo.description or "",
            "language": repo.language,
            "updated_at": repo.updated_at.isoformat() if repo.updated_at else None
        }
    
    def _scan_for_nextjs_pages(self, repo: Repository.Repository, base_path: str) -> List[str]:
        """Escanea recursivamente buscando page.tsx/jsx en Next.js App Router"""
        files = []
        try:
            contents = repo.get_contents(base_path)
            for content in contents:
                if content.type == "dir":
                    files.extend(self._scan_for_nextjs_pages(repo, content.path))
                elif content.name in ["page.tsx", "page.jsx", "page.js"]:
                    files.append(content.path)
        except:
            pass
        return files
    
    def _scan_for_react_files(self, repo: Repository.Repository, base_path: str) -> List[str]:
        """Escanea archivos React/JSX/TSX"""
        files = []
        try:
            contents = repo.get_contents(base_path)
            for content in contents:
                if content.type == "dir":
                    files.extend(self._scan_for_react_files(repo, content.path))
                elif content.name.endswith(('.tsx', '.jsx', '.js')):
                    files.append(content.path)
        except:
            pass
        return files
    
    def _scan_for_astro_files(self, repo: Repository.Repository, base_path: str) -> List[str]:
        """Escanea archivos Astro"""
        files = []
        try:
            logger.info(f"Scanning for Astro files in {base_path}")
            contents = repo.get_contents(base_path)
            for content in contents:
                if content.type == "dir":
                    files.extend(self._scan_for_astro_files(repo, content.path))
                elif content.name.endswith('.astro'):
                    logger.info(f"Found Astro file: {content.path}")
                    files.append(content.path)
        except Exception as e:
            logger.error(f"Error scanning Astro files in {base_path}: {e}")
        return files
    
    def _scan_for_html_files(self, repo: Repository.Repository, base_path: str) -> List[str]:
        """Escanea archivos HTML"""
        files = []
        try:
            contents = repo.get_contents(base_path) if base_path else repo.get_contents("")
            for content in contents:
                if content.type == "dir" and not content.name.startswith('.'):
                    files.extend(self._scan_for_html_files(repo, content.path))
                elif content.name.endswith('.html'):
                    files.append(content.path)
        except:
            pass
        return files
    
    def get_file_content(self, repo: Repository.Repository, file_path: str, ref: str = None) -> str:
        """
        Obtiene el contenido de un archivo
        
        Args:
            repo: Repository object
            file_path: Path del archivo
            ref: Branch/commit (default: default_branch)
            
        Returns:
            Contenido del archivo como string
        """
        if ref:
            file = repo.get_contents(file_path, ref=ref)
        else:
            file = repo.get_contents(file_path)
            
        return base64.b64decode(file.content).decode('utf-8')
    
    def close(self):
        """Cierra la conexión"""
        # PyGithub no requiere cierre explícito, pero lo incluimos por consistencia
        pass
