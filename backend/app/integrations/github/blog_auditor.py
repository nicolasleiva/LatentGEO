"""
Blog Auditor Service - Comprehensive blog analysis for repositories
"""
import re
from datetime import datetime
from typing import Any, Dict, List

import frontmatter

from ...core.logger import get_logger
from .client import GitHubClient

logger = get_logger(__name__)


class BlogAuditorService:
    """Audita todos los blogs de un repositorio"""

    def __init__(self, github_client: GitHubClient):
        self.client = github_client

    async def audit_all_blogs(
        self, repo_full_name: str, site_type: str
    ) -> Dict[str, Any]:
        """
        Audita todos los blogs de un repositorio

        Args:
            repo_full_name: Nombre completo del repo (owner/name)
            site_type: Tipo de sitio detectado

        Returns:
            Dict con resultados de auditoría de todos los blogs
        """
        repo = self.client.get_repo(repo_full_name)

        # 1. Encontrar archivos de blog según framework
        # Fallback: Si no se detecta tipo, usar "unknown" para activar el escaneo genérico
        if not site_type:
            site_type = "unknown"

        blog_files = self._find_blog_files(repo, site_type)

        if not blog_files:
            return {
                "status": "no_blogs_found",
                "message": f"No se encontraron blogs en {repo_full_name}",
                "site_type": site_type,
            }

        logger.info(f"Found {len(blog_files)} blog files in {repo_full_name}")

        # 2. Auditar cada blog
        blog_audits = []
        issues_summary = {
            "total_blogs": len(blog_files),
            "blogs_with_issues": 0,
            "missing_meta_description": 0,
            "missing_title": 0,
            "poor_h1": 0,
            "no_schema": 0,
            "poor_readability": 0,
            "missing_images": 0,
            "broken_structure": 0,
            "outdated_content": 0,
        }

        for blog_file in blog_files[:50]:  # Limitar a 50 para no saturar
            try:
                audit = await self._audit_single_blog(repo, blog_file, site_type)
                blog_audits.append(audit)

                # Actualizar resumen
                if audit["issues"]:
                    issues_summary["blogs_with_issues"] += 1

                for issue in audit["issues"]:
                    issue_type = issue.get("type")
                    if issue_type in issues_summary:
                        issues_summary[issue_type] += 1

            except Exception as e:
                logger.error(f"Error auditing blog {blog_file}: {e}")
                continue

        # 3. Generar reporte consolidado
        return {
            "status": "completed",
            "repo": repo_full_name,
            "site_type": site_type,
            "summary": issues_summary,
            "blogs": blog_audits,
            "audited_at": datetime.utcnow().isoformat(),
        }

    def _find_blog_files(self, repo, site_type: str) -> List[str]:
        """Encuentra archivos de blog según el framework"""
        blog_files = []

        try:
            if site_type == "nextjs":
                # Next.js: Search ALL content pages, not just blogs
                try:
                    # App Router - Find all page.tsx files
                    blog_files.extend(
                        self._scan_directory_for_pattern(
                            repo, "app", ["page.tsx", "page.jsx", "page.mdx"]
                        )
                    )
                except Exception:  # nosec B110
                    pass

                try:
                    # Pages Router - Find all .tsx files in pages
                    # Exclude _app.tsx, _document.tsx, api routes
                    pages_files = self._scan_directory_for_extension(
                        repo, "pages", [".tsx", ".jsx", ".mdx"]
                    )
                    filtered_pages = [
                        f
                        for f in pages_files
                        if not f.endswith(("_app.tsx", "_document.tsx"))
                        and "/api/" not in f
                    ]
                    blog_files.extend(filtered_pages)
                except Exception:  # nosec B110
                    pass

            elif site_type == "gatsby":
                # Gatsby: src/pages/blog/*.mdx o content/blog/*.md
                try:
                    blog_files.extend(
                        self._scan_directory_for_extension(
                            repo, "src/pages/blog", [".mdx", ".md"]
                        )
                    )
                except Exception:  # nosec B110
                    pass

                try:
                    blog_files.extend(
                        self._scan_directory_for_extension(
                            repo, "content/blog", [".mdx", ".md"]
                        )
                    )
                except Exception:  # nosec B110
                    pass

            elif site_type == "hugo":
                # Hugo: content/posts/*.md
                try:
                    blog_files.extend(
                        self._scan_directory_for_extension(
                            repo, "content/posts", [".md"]
                        )
                    )
                except Exception:  # nosec B110
                    pass

                try:
                    blog_files.extend(
                        self._scan_directory_for_extension(
                            repo, "content/blog", [".md"]
                        )
                    )
                except Exception:  # nosec B110
                    pass

            elif site_type == "jekyll":
                # Jekyll: _posts/*.md
                try:
                    blog_files.extend(
                        self._scan_directory_for_extension(
                            repo, "_posts", [".md", ".markdown"]
                        )
                    )
                except Exception:  # nosec B110
                    pass

            elif site_type == "astro":
                # Astro: src/pages/blog/*.astro o src/content/blog/*.md
                try:
                    blog_files.extend(
                        self._scan_directory_for_extension(
                            repo, "src/pages/blog", [".astro", ".md", ".mdx"]
                        )
                    )
                except Exception:  # nosec B110
                    pass

                try:
                    blog_files.extend(
                        self._scan_directory_for_extension(
                            repo, "src/content/blog", [".md", ".mdx"]
                        )
                    )
                except Exception:  # nosec B110
                    pass

            elif site_type == "vite" or site_type == "unknown":
                # Vite/SPA: archivos en raíz o src/
                logger.info(f"Scanning for Vite/SPA files in {repo.full_name}")
                # Buscar archivos principales en raíz
                try:
                    logger.info("Attempting to scan root directory...")
                    root_contents = repo.get_contents("")
                    logger.info(f"Found {len(root_contents)} items in root")
                    for content in root_contents:
                        logger.info(f"Item: {content.name}, Type: {content.type}")
                        if content.type == "file" and content.name.endswith(
                            (".tsx", ".jsx")
                        ):
                            # Excluir archivos de configuración comunes
                            if content.name not in [
                                "vite.config.tsx",
                                "vite.config.jsx",
                            ]:
                                logger.info(f"Found file: {content.path}")
                                blog_files.append(content.path)
                except Exception as e:
                    logger.error(f"Error scanning root: {e}")

                logger.info(f"Root scan found {len(blog_files)} files")

                # Buscar en src/ si existe
                try:
                    logger.info("Attempting to scan src/ directory...")
                    blog_files.extend(
                        self._scan_directory_for_extension(
                            repo, "src", [".tsx", ".jsx", ".mdx"]
                        )
                    )
                    logger.info(f"After src/ scan: {len(blog_files)} total files")
                except Exception as e:
                    logger.error(f"Error scanning src/: {e}")

        except Exception as e:
            logger.error(f"Error finding blog files: {e}")

        return blog_files

    def _scan_directory_for_pattern(
        self, repo, path: str, patterns: List[str]
    ) -> List[str]:
        """Escanea directorio buscando archivos con nombres específicos"""
        files = []
        try:
            contents = repo.get_contents(path)
            for content in contents:
                if content.type == "dir":
                    files.extend(
                        self._scan_directory_for_pattern(repo, content.path, patterns)
                    )
                elif content.name in patterns:
                    files.append(content.path)
        except Exception:  # nosec B110
            pass
        return files

    def _scan_directory_for_extension(
        self, repo, path: str, extensions: List[str]
    ) -> List[str]:
        """Escanea directorio buscando archivos con extensiones específicas"""
        files = []
        try:
            contents = repo.get_contents(path)
            for content in contents:
                if content.type == "dir":
                    files.extend(
                        self._scan_directory_for_extension(
                            repo, content.path, extensions
                        )
                    )
                elif any(content.name.endswith(ext) for ext in extensions):
                    files.append(content.path)
        except Exception:  # nosec B110
            pass
        return files

    async def _audit_single_blog(
        self, repo, file_path: str, site_type: str
    ) -> Dict[str, Any]:
        """
        Audita un blog individual

        Returns:
            Dict con resultados de auditoría del blog
        """
        # Obtener contenido
        content = self.client.get_file_content(repo, file_path)

        # Parsear según tipo de archivo
        blog_data = self._parse_blog_content(content, file_path, site_type)

        # Auditar contenido
        issues = []

        # 1. Meta Description
        if not blog_data.get("meta_description"):
            issues.append(
                {
                    "type": "missing_meta_description",
                    "severity": "critical",
                    "message": "Blog post missing meta description",
                    "recommendation": "Add SEO-optimized meta description (150-160 chars)",
                }
            )
        elif len(blog_data.get("meta_description", "")) < 120:
            issues.append(
                {
                    "type": "missing_meta_description",
                    "severity": "high",
                    "message": f"Meta description too short ({len(blog_data['meta_description'])} chars)",
                    "recommendation": "Expand to 150-160 characters",
                }
            )

        # 2. Title
        if not blog_data.get("title"):
            issues.append(
                {
                    "type": "missing_title",
                    "severity": "critical",
                    "message": "Blog post missing title",
                    "recommendation": "Add descriptive title (50-60 chars)",
                }
            )
        elif len(blog_data.get("title", "")) > 70:
            issues.append(
                {
                    "type": "missing_title",
                    "severity": "medium",
                    "message": f"Title too long ({len(blog_data['title'])} chars)",
                    "recommendation": "Shorten to 50-60 characters",
                }
            )

        # 3. H1
        if not blog_data.get("h1"):
            issues.append(
                {
                    "type": "poor_h1",
                    "severity": "critical",
                    "message": "Blog post missing H1 heading",
                    "recommendation": "Add single H1 with primary keyword",
                }
            )
        elif blog_data.get("h1_count", 0) > 1:
            issues.append(
                {
                    "type": "poor_h1",
                    "severity": "high",
                    "message": f"Multiple H1 tags found ({blog_data['h1_count']})",
                    "recommendation": "Use only one H1 per page",
                }
            )

        # 4. Schema Markup
        if not blog_data.get("has_schema"):
            issues.append(
                {
                    "type": "no_schema",
                    "severity": "high",
                    "message": "Blog post missing structured data (schema.org)",
                    "recommendation": "Add Article schema with author, date, publisher",
                }
            )

        # 5. Readability
        word_count = blog_data.get("word_count", 0)
        if word_count < 300:
            issues.append(
                {
                    "type": "poor_readability",
                    "severity": "high",
                    "message": f"Blog post too short ({word_count} words)",
                    "recommendation": "Expand to at least 800-1000 words for SEO",
                }
            )

        # 6. Images
        if not blog_data.get("has_images"):
            issues.append(
                {
                    "type": "missing_images",
                    "severity": "medium",
                    "message": "Blog post has no images",
                    "recommendation": "Add at least 1-2 relevant images with alt text",
                }
            )
        elif blog_data.get("images_without_alt", 0) > 0:
            issues.append(
                {
                    "type": "missing_images",
                    "severity": "medium",
                    "message": f"{blog_data['images_without_alt']} images missing alt text",
                    "recommendation": "Add descriptive alt text to all images",
                }
            )

        # 7. Headings Structure
        if not blog_data.get("has_h2"):
            issues.append(
                {
                    "type": "broken_structure",
                    "severity": "medium",
                    "message": "Blog post missing H2 subheadings",
                    "recommendation": "Add H2/H3 structure for better scannability",
                }
            )

        # 8. Freshness (si hay fecha)
        if blog_data.get("published_date"):
            try:
                pub_date = datetime.fromisoformat(
                    blog_data["published_date"].replace("Z", "+00:00")
                )
                age_days = (datetime.now(pub_date.tzinfo) - pub_date).days

                if age_days > 365:
                    issues.append(
                        {
                            "type": "outdated_content",
                            "severity": "low",
                            "message": f"Blog post is {age_days} days old",
                            "recommendation": "Consider updating with fresh statistics/information",
                        }
                    )
            except Exception:  # nosec B110
                pass

        return {
            "file_path": file_path,
            "title": blog_data.get("title", "Untitled"),
            "url_slug": self._extract_slug_from_path(file_path),
            "word_count": blog_data.get("word_count", 0),
            "published_date": blog_data.get("published_date"),
            "author": blog_data.get("author"),
            "issues": issues,
            "issue_count": len(issues),
            "severity_score": self._calculate_severity_score(issues),
        }

    def _parse_blog_content(
        self, content: str, file_path: str, site_type: str
    ) -> Dict[str, Any]:
        """
        Parsea contenido del blog y extrae metadata

        Returns:
            Dict con datos parseados del blog
        """
        data = {
            "title": None,
            "meta_description": None,
            "h1": None,
            "h1_count": 0,
            "has_h2": False,
            "has_schema": False,
            "has_images": False,
            "images_without_alt": 0,
            "word_count": 0,
            "published_date": None,
            "author": None,
        }

        # Markdown con frontmatter (Hugo, Jekyll, Gatsby)
        if file_path.endswith((".md", ".mdx", ".markdown")):
            try:
                post = frontmatter.loads(content)

                # Metadata del frontmatter
                data["title"] = post.metadata.get("title")
                data["meta_description"] = post.metadata.get("description")
                data["published_date"] = str(post.metadata.get("date", ""))
                data["author"] = post.metadata.get("author")

                # Analizar contenido markdown
                html_content = post.content
                data["word_count"] = len(html_content.split())

                # Buscar headings
                h1_matches = re.findall(r"^#\s+(.+)$", html_content, re.MULTILINE)
                data["h1"] = h1_matches[0] if h1_matches else None
                data["h1_count"] = len(h1_matches)

                h2_matches = re.findall(r"^##\s+(.+)$", html_content, re.MULTILINE)
                data["has_h2"] = len(h2_matches) > 0

                # Buscar imágenes
                img_matches = re.findall(r"!\[([^\]]*)\]\(([^)]+)\)", html_content)
                data["has_images"] = len(img_matches) > 0
                data["images_without_alt"] = len(
                    [img for img in img_matches if not img[0]]
                )

            except Exception as e:
                logger.debug(f"Error parsing markdown frontmatter: {e}")
                # Fallback: parsear como texto plano
                data["word_count"] = len(content.split())

        # React/Next.js/Astro components
        elif file_path.endswith((".tsx", ".jsx", ".astro")):
            # Buscar metadata export en Next.js
            metadata_match = re.search(
                r"export\s+const\s+metadata\s*=\s*\{([^}]+)\}", content, re.DOTALL
            )
            if metadata_match:
                metadata_str = metadata_match.group(1)

                title_match = re.search(r'title:\s*["\']([^"\']+)["\']', metadata_str)
                if title_match:
                    data["title"] = title_match.group(1)

                desc_match = re.search(
                    r'description:\s*["\']([^"\']+)["\']', metadata_str
                )
                if desc_match:
                    data["meta_description"] = desc_match.group(1)

            # Buscar JSX content
            data["word_count"] = len(re.sub(r"<[^>]+>", "", content).split())

            # H1 en JSX
            h1_matches = re.findall(r"<h1[^>]*>([^<]+)</h1>", content)
            data["h1"] = h1_matches[0] if h1_matches else None
            data["h1_count"] = len(h1_matches)

            # H2 en JSX
            h2_matches = re.findall(r"<h2[^>]*>", content)
            data["has_h2"] = len(h2_matches) > 0

            # Imágenes
            img_matches = re.findall(r"<img[^>]*>", content)
            data["has_images"] = len(img_matches) > 0

            imgs_with_alt = len(
                re.findall(r'<img[^>]*alt=["\'][^"\']+["\'][^>]*>', content)
            )
            data["images_without_alt"] = len(img_matches) - imgs_with_alt

            # Schema check
            data["has_schema"] = (
                "application/ld+json" in content or "schema.org" in content
            )

        return data

    def _extract_slug_from_path(self, file_path: str) -> str:
        """Extrae slug de la URL del path del archivo"""
        # app/blog/my-post/page.tsx -> my-post
        # content/posts/2024-01-15-my-post.md -> my-post

        parts = file_path.split("/")

        # Casos especiales
        if "page.tsx" in file_path or "page.jsx" in file_path:
            # Next.js App Router: /blog/[slug]/page.tsx
            return parts[-2] if len(parts) > 2 else parts[-1]

        # Markdown files
        filename = (
            parts[-1].replace(".md", "").replace(".mdx", "").replace(".markdown", "")
        )

        # Remover prefijos de fecha (Jekyll style)
        filename = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", filename)

        return filename

    def _calculate_severity_score(self, issues: List[Dict]) -> int:
        """
        Calcula score de severidad (0-100, donde 100 es peor)

        Returns:
            Score de severidad
        """
        score = 0

        for issue in issues:
            severity = issue.get("severity", "low")
            if severity == "critical":
                score += 25
            elif severity == "high":
                score += 15
            elif severity == "medium":
                score += 8
            elif severity == "low":
                score += 3

        return min(score, 100)

    def generate_fixes_from_audit(
        self, blog_audit: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Genera lista de fixes aplicables desde una auditoría de blog

        Args:
            blog_audit: Resultado de _audit_single_blog

        Returns:
            Lista de fixes en formato compatible con create_pr
        """
        fixes = []

        for issue in blog_audit.get("issues", []):
            issue_type = issue.get("type")

            fix = {
                "type": self._map_blog_issue_to_fix_type(issue_type),
                "priority": self._severity_to_priority(issue.get("severity")),
                "page_url": blog_audit.get("url_slug", ""),
                "file_path": blog_audit.get("file_path"),
                "description": issue.get("message"),
                "value": issue.get("recommendation"),
            }

            fixes.append(fix)

        return fixes

    def _map_blog_issue_to_fix_type(self, issue_type: str) -> str:
        """Mapea tipo de issue de blog a tipo de fix"""
        mapping = {
            "missing_meta_description": "meta_description",
            "missing_title": "title",
            "poor_h1": "h1",
            "no_schema": "schema",
            "missing_images": "alt_text",
            "broken_structure": "structure",
            "outdated_content": "content_refresh",
            "poor_readability": "content_enhancement",
        }
        return mapping.get(issue_type, "other")

    def _severity_to_priority(self, severity: str) -> str:
        """Convierte severidad a prioridad"""
        mapping = {
            "critical": "CRITICAL",
            "high": "HIGH",
            "medium": "MEDIUM",
            "low": "LOW",
        }
        return mapping.get(severity, "MEDIUM")
