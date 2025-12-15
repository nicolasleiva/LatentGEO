import requests
from github import Github, GithubException
from typing import List, Dict, Optional

from app.core.config import settings
from app.schemas.github import GitHubRepo, GitHubUser
from app.core.logger import get_logger

logger = get_logger(__name__)

class GitHubService:
    """
    Servicio para interactuar con la API de GitHub.
    """

    @staticmethod
    def get_auth_url() -> str:
        """Genera la URL de autorización de GitHub OAuth."""
        client_id = settings.GITHUB_CLIENT_ID
        redirect_uri = settings.GITHUB_REDIRECT_URI
        scope = "repo,user"
        return f"https://github.com/login/oauth/authorize?client_id={client_id}&redirect_uri={redirect_uri}&scope={scope}"

    @staticmethod
    def exchange_code_for_token(code: str) -> Optional[str]:
        """Intercambia un código de autorización por un token de acceso."""
        client_id = settings.GITHUB_CLIENT_ID
        client_secret = settings.GITHUB_CLIENT_SECRET
        
        url = "https://github.com/login/oauth/access_token"
        headers = {"Accept": "application/json"}
        data = {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
        }
        
        try:
            response = requests.post(url, headers=headers, data=data)
            response.raise_for_status()
            token_data = response.json()
            return token_data.get("access_token")
        except requests.RequestException as e:
            logger.error(f"Error exchanging GitHub code for token: {e}")
            return None

    @staticmethod
    def get_user_info(access_token: str) -> Optional[GitHubUser]:
        """Obtiene información del usuario autenticado."""
        try:
            g = Github(access_token)
            user = g.get_user()
            return GitHubUser(
                login=user.login,
                avatar_url=user.avatar_url,
                html_url=user.html_url
            )
        except GithubException as e:
            logger.error(f"Error getting user info from GitHub: {e}")
            return None

    @staticmethod
    def get_user_repos(access_token: str) -> List[GitHubRepo]:
        """Obtiene los repositorios de un usuario."""
        try:
            g = Github(access_token)
            user = g.get_user()
            repos = []
            for repo in user.get_repos(sort="updated"):
                repos.append(GitHubRepo(
                    id=repo.id,
                    name=repo.name,
                    full_name=repo.full_name,
                    private=repo.private,
                    html_url=repo.html_url,
                    description=repo.description
                ))
            return repos
        except GithubException as e:
            logger.error(f"Error getting user repos from GitHub: {e}")
            return []

    @staticmethod
    def create_fix_pr(
        access_token: str,
        repo_full_name: str,
        base_branch: str,
        new_branch_name: str,
        commit_message: str,
        pr_title: str,
        pr_body: str,
        files_to_commit: Dict[str, str]
    ) -> Optional[str]:
        """Crea un Pull Request con los archivos corregidos."""
        try:
            g = Github(access_token)
            repo = g.get_repo(repo_full_name)
            
            # 1. Crear nueva rama desde la base
            source = repo.get_branch(base_branch)
            repo.create_git_ref(ref=f"refs/heads/{new_branch_name}", sha=source.commit.sha)
            
            # 2. Hacer commit de los cambios
            for file_path, content in files_to_commit.items():
                try:
                    # Actualizar archivo si existe
                    file_content = repo.get_contents(file_path, ref=new_branch_name)
                    repo.update_file(file_path, commit_message, content, file_content.sha, branch=new_branch_name)
                except GithubException:
                    # Crear archivo si no existe
                    repo.create_file(file_path, commit_message, content, branch=new_branch_name)
            
            # 3. Crear el Pull Request
            pr = repo.create_pull(title=pr_title, body=pr_body, head=new_branch_name, base=base_branch)
            return pr.html_url
        except GithubException as e:
            logger.error(f"Failed to create Pull Request in {repo_full_name}: {e}")
            return None