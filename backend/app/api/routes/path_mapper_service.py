from typing import List, Dict, Set
from github import Github, ContentFile
from app.core.logger import get_logger

logger = get_logger(__name__)

class PathMapperService:
    """
    Servicio para mapear rutas de URL de una auditoría a rutas de archivos en un repositorio de GitHub.
    """

    @staticmethod
    def get_all_repo_files(repo) -> List[ContentFile]:
        """
        Obtiene una lista plana de todos los archivos en el repositorio.
        """
        try:
            contents = repo.get_contents("")
            all_files = []
            while contents:
                file_content = contents.pop(0)
                if file_content.type == "dir":
                    contents.extend(repo.get_contents(file_content.path))
                else:
                    all_files.append(file_content)
            return all_files
        except Exception as e:
            logger.error(f"Error getting all repo files for {repo.full_name}: {e}")
            return []

    @staticmethod
    def map_urls_to_files(fix_plan: List[Dict], repo_files: List[ContentFile]) -> Dict[str, str]:
        """
        Intenta mapear las page_path del fix_plan a archivos reales del repositorio.
        Devuelve un diccionario {page_path_from_audit: file_path_in_repo}.
        """
        url_paths_to_fix = {item['page_path'] for item in fix_plan if 'page_path' in item and item['page_path'] != 'ALL_PAGES'}
        
        if not url_paths_to_fix:
            return {}

        mapping = {}
        
        # Heurísticas para frameworks comunes (Next.js, Astro, etc.)
        # Esto se puede expandir enormemente.
        possible_extensions = ['.js', '.jsx', '.ts', '.tsx', '.astro', '.html', '.md', '.mdx']

        for url_path in url_paths_to_fix:
            # Normalizar path: /about-us -> about-us
            clean_path = url_path.strip('/')
            if not clean_path: # Si es la página de inicio
                clean_path = 'index'

            best_match = None
            
            for file in repo_files:
                file_path_lower = file.path.lower()
                
                # Eliminar extensiones y partes como 'src/pages' o 'app/' para comparar
                base_name = file_path_lower
                for ext in possible_extensions:
                    if base_name.endswith(ext):
                        base_name = base_name[:-len(ext)]
                        break
                
                base_name = base_name.replace('src/pages/', '').replace('app/', '').strip('/')
                if base_name.endswith('/index') or base_name.endswith('/page'):
                    base_name = base_name.rsplit('/', 1)[0]

                if base_name == clean_path:
                    best_match = file.path
                    break # Encontramos una coincidencia exacta

            if best_match:
                mapping[url_path] = best_match
        
        logger.info(f"Path mapping found: {mapping}")
        return mapping