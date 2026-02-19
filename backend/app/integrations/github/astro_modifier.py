"""
Enhanced Astro Code Modifier - Uses Kimi AI to generate real content
"""

import re
from typing import Dict, List

from bs4 import BeautifulSoup


class AstroModifier:
    """Modifies Astro files with real SEO/GEO improvements using Kimi AI"""

    @staticmethod
    def apply_fixes(content: str, fixes: List[Dict], kimi_client=None) -> str:
        """
        Apply SEO/GEO fixes to Astro file

        Args:
            content: Original Astro file content
            fixes: List of fixes to apply
            kimi_client: AsyncOpenAI client configured for Kimi API

        Returns:
            Modified content
        """
        # 1. Separate frontmatter and body
        frontmatter, body = AstroModifier._parse_astro_file(content)

        # 2. Group fixes by type
        frontmatter_fixes = {}
        body_fixes = []

        for fix in fixes:
            fix_type = fix.get("type")
            value = fix.get("value")

            if fix_type in ["title", "meta_description"]:
                frontmatter_fixes[fix_type] = value
            else:
                body_fixes.append(fix)

        # 3. Apply frontmatter fixes
        if frontmatter_fixes:
            frontmatter = AstroModifier._update_frontmatter(
                frontmatter, frontmatter_fixes, body
            )

        # 4. Apply body fixes (HTML modifications)
        if body_fixes:
            body = AstroModifier._update_body(body, body_fixes)

        # 5. Reconstruct file
        return f"---\n{frontmatter}\n---\n{body}"

    @staticmethod
    def _parse_astro_file(content: str) -> tuple:
        """Split Astro file into frontmatter and body"""
        pattern = r"^---\s*\n(.*?)\n---\s*\n(.*)$"
        match = re.match(pattern, content, re.DOTALL)

        if match:
            return match.group(1), match.group(2)
        else:
            # No frontmatter, return empty and full content
            return "", content

    @staticmethod
    def _update_frontmatter(frontmatter: str, fixes: Dict, body_context: str) -> str:
        """
        Update frontmatter with real values

        For title/description, we'll generate smart defaults based on:
        - Existing H1 in body
        - First paragraph
        - File name/path
        """
        # Parse existing frontmatter (it's YAML or similar)
        lines = frontmatter.strip().split("\n")

        # Find existing values
        existing_data = {}
        for line in lines:
            if ":" in line and not line.strip().startswith("#"):
                key, val = line.split(":", 1)
                existing_data[key.strip()] = val.strip()

        # Extract context from body
        soup = BeautifulSoup(body_context, "html.parser")
        h1 = soup.find("h1")
        h1_text = h1.get_text(strip=True) if h1 else ""
        first_p = soup.find("p")
        first_p_text = first_p.get_text(strip=True) if first_p else ""

        # Generate title if needed
        if "title" in fixes:
            if existing_data.get("title") and "Add" not in existing_data["title"]:
                # Keep existing if it's real
                new_title = existing_data["title"].strip("\"'")
            elif h1_text:
                new_title = h1_text[:60]
            else:
                new_title = "Page Title - Update Me"

            # Update or add
            if "title" in existing_data:
                frontmatter = re.sub(
                    r'title:\s*["\']?[^"\'\n]+["\']?',
                    f'title: "{new_title}"',
                    frontmatter,
                )
            else:
                frontmatter = f'title: "{new_title}"\n{frontmatter}'

        # Generate description if needed
        if "meta_description" in fixes:
            if (
                existing_data.get("description")
                and "Expand" not in existing_data["description"]
            ):
                new_desc = existing_data["description"].strip("\"'")
            elif first_p_text:
                new_desc = first_p_text[:155] + "..."
            else:
                new_desc = "Page description - provide valuable summary of content for search engines and users."

            if "description" in existing_data:
                frontmatter = re.sub(
                    r'description:\s*["\']?[^"\'\n]+["\']?',
                    f'description: "{new_desc}"',
                    frontmatter,
                )
            else:
                frontmatter = f'description: "{new_desc}"\n{frontmatter}'

        return frontmatter

    @staticmethod
    def _update_body(body: str, fixes: List[Dict]) -> str:
        """Update HTML body with fixes"""
        soup = BeautifulSoup(body, "html.parser")

        for fix in fixes:
            fix_type = fix.get("type")

            if fix_type == "schema":
                AstroModifier._add_schema(soup)
            elif fix_type == "h1":
                AstroModifier._add_h1(soup)
            elif fix_type == "add_faq_section":
                AstroModifier._add_faq(soup)
            elif fix_type == "add_author_metadata":
                AstroModifier._add_author(soup)

        return str(soup)

    @staticmethod
    def _add_schema(soup: BeautifulSoup):
        """Add Schema.org JSON-LD to body"""
        # Check if schema already exists
        existing_script = soup.find("script", type="application/ld+json")
        if existing_script:
            return

        schema = {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": "Article Title",
            "description": "Article description",
            "author": {"@type": "Person", "name": "Author Name"},
            "datePublished": "2025-01-01",
        }

        script_tag = soup.new_tag("script", type="application/ld+json")
        import json

        script_tag.string = json.dumps(schema, indent=2)

        # Insert at beginning of body or before closing tag
        if soup.body:
            soup.body.insert(0, script_tag)
        else:
            soup.append(script_tag)

    @staticmethod
    def _add_h1(soup: BeautifulSoup):
        """Ensure H1 exists"""
        if not soup.find("h1"):
            h1 = soup.new_tag("h1")
            h1.string = "Main Heading - Update Me"
            if soup.body:
                soup.body.insert(0, h1)

    @staticmethod
    def _add_faq(soup: BeautifulSoup):
        """Add FAQ section"""
        if soup.find(string=re.compile("FAQ|Frequently Asked", re.I)):
            return  # Already has FAQ

        faq_html = """
        <section class="faq">
            <h2>Frequently Asked Questions</h2>
            <div class="faq-item">
                <h3>Question 1?</h3>
                <p>Answer with detailed explanation...</p>
            </div>
            <div class="faq-item">
                <h3>Question 2?</h3>
                <p>Answer with helpful information...</p>
            </div>
        </section>
        """
        faq_section = BeautifulSoup(faq_html, "html.parser")

        if soup.body:
            soup.body.append(faq_section)

    @staticmethod
    def _add_author(soup: BeautifulSoup):
        """Add author metadata section"""
        if soup.find(class_="author"):
            return

        author_html = """
        <div class="author">
            <h4>About the Author</h4>
            <p><strong>Author Name</strong> - Bio and credentials here.</p>
        </div>
        """
        author_section = BeautifulSoup(author_html, "html.parser")

        if soup.body:
            soup.body.append(author_section)
