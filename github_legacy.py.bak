from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.responses import RedirectResponse
from typing import List

from app.services.github_service import GitHubService
from app.schemas.github import GitHubRepo, GitHubUser

router = APIRouter(
    prefix="/github",
    tags=["github"],
    responses={404: {"description": "Not found"}},
)

@router.get("/login")
def github_login():
    """Redirige al usuario a GitHub para autorizar la aplicación."""
    auth_url = GitHubService.get_auth_url()
    return RedirectResponse(url=auth_url)

@router.get("/callback")
def github_callback(code: str, response: Response):
    """
    Callback de GitHub. Intercambia el código por un token y lo guarda en una cookie.
    """
    access_token = GitHubService.exchange_code_for_token(code)
    if not access_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not retrieve access token from GitHub.")
    
    # Guardar el token en una httpOnly cookie segura
    response.set_cookie(
        key="github_access_token",
        value=access_token,
        httponly=True,
        secure=True, # Poner en False solo para desarrollo local si no usas HTTPS
        samesite="lax",
        max_age=3600 * 24 * 7 # 1 semana
    )
    # Redirigir al dashboard o a una página de éxito
    return {"message": "Successfully authenticated with GitHub. You can now close this window."}

@router.get("/repos", response_model=List[GitHubRepo])
def get_repos(request: Request):
    """Obtiene la lista de repositorios del usuario autenticado."""
    access_token = request.cookies.get("github_access_token")
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated with GitHub.")
    
    repos = GitHubService.get_user_repos(access_token)
    return repos