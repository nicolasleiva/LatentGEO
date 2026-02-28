"""
Professional Next.js Code Modifier - Production Ready
Uses Kimi AI for intelligent JSX transformations
Handles ALL fix types: metadata, Schema.org, FAQs, heading hierarchy, etc.
"""

import json
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional

from openai import OpenAI
from bs4 import BeautifulSoup

from ...core.config import settings
from ...core.external_resilience import run_external_call_sync

logger = logging.getLogger(__name__)


class NextJsModifier:
    """Production-ready Next.js file modifier with AI-powered transformations"""

    @staticmethod
    def apply_fixes(
        content: str, fixes: List[Dict], file_path: str, audit_context: Dict = None
    ) -> str:
        """
        Apply ALL SEO/GEO fixes to Next.js file using Kimi AI
        """
        try:
            modifier = NextJsModifier()
            return modifier._apply_fixes_internal(
                content, fixes, file_path, audit_context
            )
        except Exception as e:
            logger.error(f"Error in NextJsModifier: {e}")
            return content

    def _apply_fixes_internal(
        self,
        content: str,
        fixes: List[Dict],
        file_path: str,
        audit_context: Dict = None,
    ) -> str:
        """Internal implementation with full JSX transformation"""
        normalized_path = file_path.replace("\\", "/")
        is_app_router = (
            normalized_path.startswith("app/")
            or "/app/" in normalized_path
            or "export const metadata" in content
        )

        logger.info(
            f"NextJsModifier: Processing {file_path}, App Router: {is_app_router}, Fixes: {len(fixes)}"
        )

        # Group fixes by category
        metadata_fixes = []
        structural_fixes = []
        content_fixes = []

        for fix in fixes:
            fix_type = fix.get("type")
            if fix_type in ["title", "meta_description"]:
                metadata_fixes.append(fix)
            elif fix_type in ["h1", "structure", "schema", "alt_text"]:
                structural_fixes.append(fix)
            elif fix_type in [
                "add_faq_section",
                "add_author_metadata",
                "add_citations",
                "add_statistics",
                "restructure_intro",
                "add_lists_tables",
                "add_case_study",
                "content_enhancement",
            ]:
                content_fixes.append(fix)

        modified_content = content

        # Phase 1: Apply metadata with Kimi (fast, high-value) - App Router specific
        if metadata_fixes and is_app_router:
            modified_content = self._update_metadata_with_kimi(
                modified_content,
                file_path,
                audit_context,
                metadata_fixes=metadata_fixes,
            )
            # Remove from further processing if handled by _update_metadata_with_kimi
            metadata_fixes = []

        # Phase 2: Apply structural + content fixes + metadata fixes (if not handled) with comprehensive Kimi transformation
        if structural_fixes or content_fixes or metadata_fixes:
            modified_content = self._apply_comprehensive_jsx_fixes(
                modified_content,
                structural_fixes + content_fixes + metadata_fixes,
                file_path,
                audit_context,
            )

        if modified_content != content:
            logger.info(
                f"Successfully modified {file_path} ({len(fixes)} fixes applied)"
            )
        else:
            logger.warning(f"No changes made to {file_path}")

        return modified_content

    def _update_metadata_with_kimi(
        self,
        content: str,
        file_path: str,
        audit_context: Dict = None,
        metadata_fixes: Optional[List[Dict]] = None,
    ) -> str:
        """Generate and insert smart metadata using Kimi AI (or user-provided overrides)."""
        has_metadata = re.search(r"export\s+const\s+metadata\s*=", content)
        context = self._extract_file_context(content, file_path)

        override_title = None
        override_desc = None
        if metadata_fixes:
            for fix in metadata_fixes:
                if fix.get("type") == "title" and fix.get("value"):
                    override_title = str(fix.get("value")).strip()
                if fix.get("type") == "meta_description" and fix.get("value"):
                    override_desc = str(fix.get("value")).strip()

        metadata = None
        if not override_title or not override_desc:
            metadata = self._generate_metadata_with_kimi(context, audit_context)
        title_value = override_title or (metadata.get("title") if metadata else "")
        desc_value = override_desc or (metadata.get("description") if metadata else "")

        if has_metadata:
            pattern = r"export\s+const\s+metadata\s*=\s*\{[^}]+\}"
            replacement = f"""export const metadata = {{
  title: {json.dumps(title_value)},
  description: {json.dumps(desc_value)}
}}"""
            return re.sub(pattern, replacement, content, flags=re.DOTALL)
        else:
            last_import = 0
            for match in re.finditer(r"^import .*", content, re.MULTILINE):
                last_import = match.end()

            metadata_block = f"""\n
export const metadata = {{
  title: {json.dumps(title_value)},
  description: {json.dumps(desc_value)}
}}
"""
            if last_import > 0:
                return content[:last_import] + metadata_block + content[last_import:]
            else:
                return metadata_block + content

    def _apply_comprehensive_jsx_fixes(
        self,
        content: str,
        fixes: List[Dict],
        file_path: str,
        audit_context: Dict = None,
    ) -> str:
        """
        Use Kimi AI to apply comprehensive JSX transformations
        Handles: Schema.org, FAQs, heading hierarchy, content enhancements, etc.
        """
        if not fixes:
            return content

        # Build detailed instructions for Kimi
        instructions = self._build_transformation_instructions(fixes)

        # Extract context
        context = self._extract_file_context(content, file_path)

        # Build prompt with audit context if available
        audit_info = ""
        if audit_context:
            # Format PageSpeed Data
            ps_info = "Not available"
            if audit_context.get("pagespeed"):
                ps = audit_context["pagespeed"]
                ps_info = f"Score: {ps.get('score')}, LCP: {ps.get('metrics', {}).get('LCP')}, CLS: {ps.get('metrics', {}).get('CLS')}"
                if ps.get("opportunities"):
                    ps_info += f"\n  Opportunities: {', '.join([o['title'] for o in ps['opportunities'][:3]])}"

            # Format Technical Audit
            tech_info = "Not available"
            if audit_context.get("technical_audit"):
                ta = audit_context["technical_audit"]
                tech_info = f"Schema: {ta.get('schema_status')}, H1: {ta.get('h1_status')}, Semantic HTML: {ta.get('semantic_html_score')}%"

            # Format Content Suggestions
            content_ideas = "None"
            if audit_context.get("content_suggestions"):
                content_ideas = "\n  - ".join(
                    [
                        f"{s['topic']} ({s['type']}): {s['suggestion']}"
                        for s in audit_context["content_suggestions"][:3]
                    ]
                )

            audit_info = f"""
AUDIT CONTEXT (Use this to generate highly relevant and optimized content):
- Target Keywords: {', '.join(audit_context.get('keywords', [])[:10])}
- Main Competitors: {', '.join(audit_context.get('competitors', [])[:3])}
- Critical Issues: {', '.join(audit_context.get('issues', [])[:5])}
- PageSpeed Insights: {ps_info}
- Technical Status: {tech_info}
- AI Content Ideas to Integrate:
  - {content_ideas}
- Industry/Topic: {audit_context.get('topic', 'Growth Hacking & SEO')}
"""

        user_data_lines = []
        for fix in fixes:
            if fix.get("value") is None:
                continue
            fix_type = fix.get("type")
            value = fix.get("value")
            try:
                value_dump = json.dumps(value, ensure_ascii=False)
            except Exception:
                value_dump = str(value)
            if fix_type == "h1":
                user_data_lines.append(f"- H1: {value_dump}")
            elif fix_type == "schema":
                user_data_lines.append(f"- Schema org data: {value_dump}")
            elif fix_type == "add_author_metadata":
                user_data_lines.append(f"- Author data: {value_dump}")
            elif fix_type == "add_faq_section":
                user_data_lines.append(f"- FAQ data: {value_dump}")
            elif fix_type == "title":
                user_data_lines.append(f"- Title: {value_dump}")
            elif fix_type == "meta_description":
                user_data_lines.append(f"- Meta description: {value_dump}")

        user_data_block = ""
        if user_data_lines:
            user_data_block = (
                "USER-PROVIDED DATA (MUST USE VERBATIM; DO NOT INVENT):\n"
                + "\n".join(user_data_lines)
                + "\n"
            )

        has_faq_fix = any(
            fix.get("type") == "add_faq_section" and fix.get("value") for fix in fixes
        )
        has_author_fix = any(
            fix.get("type") == "add_author_metadata" and fix.get("value")
            for fix in fixes
        )

        content_rules = [
            f"- Use current year: {datetime.now().strftime('%Y')}",
            "- All image URLs must be relative paths (e.g., /og-image.jpg, /logo.jpg)",
            "- Dates must be realistic (not placeholder dates)",
            "- Verify all referenced images exist in public/ directory",
        ]
        if has_faq_fix:
            content_rules.append(
                "- Add FAQ section ONLY with the user-provided Q&A pairs."
            )
        else:
            content_rules.append(
                "- Do NOT add FAQ content unless explicitly requested in transformations."
            )
        if has_author_fix:
            content_rules.append(
                "- Add author section ONLY with user-provided author data."
            )
        else:
            content_rules.append(
                "- Do NOT add author sections unless explicitly requested in transformations."
            )

        prompt = f"""You are a senior React/Next.js and SEO expert. Transform this TSX file to improve SEO/GEO performance.

FILE: {file_path}
CONTEXT: {context['file_name']} - Headings: {', '.join(context['headings'][:3]) if context['headings'] else 'None'}
{audit_info}
{user_data_block}

CURRENT CODE:
```tsx
{content}
```

REQUIRED TRANSFORMATIONS ({len(fixes)} total):
{instructions}

=== CRITICAL RULES (MUST FOLLOW EXACTLY) ===

1. RESPONSE FORMAT:
   - Return ONLY the complete modified TSX code
   - NO explanations, NO markdown code blocks (no ```)
   - Do NOT truncate or summarize
   - Do NOT include any text before or after the code
   - Do NOT include markdown descriptions like "Here's the complete modified TSX file..."

2. PRESERVE EXISTING CODE:
   - Keep ALL existing imports, props, state, and component logic
   - Keep consistent code style with original file

=== NEXT.JS APP ROUTER RULES ===

3. METADATA (for App Router):
   - Use `export const metadata = {{...}}` for title/description
   - Do NOT import 'next/head' - that's Pages Router only
   - JSON-LD in body IS valid in App Router

4. STRUCTURED DATA - CORRECT PATTERN (Validation Strict):
   ```tsx
   // STEP 1: Define schema data OUTSIDE component
   // IMPORTANT: Keep metadata strings in variables to sync between export metadata and schema
   const SITE_TITLE = "...";
   const SITE_DESC = "...";

   export const metadata = {{
     title: SITE_TITLE,
     description: SITE_DESC
   }}

   const structuredData = {{
     "@context": "https://schema.org",
     "@type": "WebPage",
     "headline": SITE_TITLE,  // SYNC with metadata
     "description": SITE_DESC, // SYNC with metadata
     "author": {{ "@type": "Organization", "name": "Our Team" }},
     "datePublished": "{datetime.now().strftime('%Y')}-01-01",
     "image": "/og-image.jpg"
   }}

   const faqData = {{
     "@context": "https://schema.org",
     "@type": "FAQPage",
     "mainEntity": [
       {{ "@type": "Question", "name": "...", "acceptedAnswer": {{ "@type": "Answer", "text": "..." }} }}
     ]
   }}

   // STEP 2: Injection 
   // Note: Since we have @context in each object, we can inject them as an array or graph.
   // Best practice for Next.js App Router:
   export default function Page() {{
     return (
       <main>
         <script
            type="application/ld+json"
            dangerouslySetInnerHTML={{{{ __html: JSON.stringify([structuredData, faqData]) }}}}
         />
         ...
       </main>
     )
   }}
   ```

5. FAQ SECTION - DYNAMIC RENDERING (React Best Practices):
   - Iterate over `faqData.mainEntity` to render questions.
   - IMPORANT: Use a unique property (like `faq.name`) as the `key` prop.
   - DO NOT use the array index `key={{index}}` (this is an anti-pattern).
   - Example: `<div key={{faq.name}}>...</div>`

6. THINGS TO AVOID:
   ❌ Don't use "https://example.com/..." URLs (use relative paths)
   ❌ Don't define structured data INSIDE component (causes re-render)
   ❌ Don't use array index as React key (key={{index}} is BAD)
   ❌ Don't desynchronize metadata title/desc from schema headline/desc
   ❌ Don't import next/head in App Router
   ❌ Don't duplicate FAQ content (schema AND hardcoded HTML)
   ❌ Don't import next/head in App Router
   ❌ Don't add markdown text or code fence markers (```tsx, ```) at the start or end
   ❌ Don't use placeholder dates like "2025-01-01" (use current year)
   ❌ Don't reference non-existent image files (/og-image.jpg must exist in public/)
   ❌ Don't use itemProp="mainEntity" on individual FAQ items (only on container)
   ❌ Don't include explanatory text like "Here's the complete modified TSX file..."

7. CONTENT RULES:
   {chr(10).join(content_rules)}

IMPORTANT: Return the ENTIRE modified file. Do not truncate.
"""

        try:
            # Usar Devstral para código (optimizado para programación)
            api_key = (
                settings.NV_API_KEY_CODE
                or settings.NVIDIA_API_KEY
                or settings.NV_API_KEY
            )
            client = OpenAI(api_key=api_key, base_url=settings.NV_BASE_URL)

            logger.info(
                f"Calling Devstral (code-optimized) for JSX transformation of {file_path}"
            )

            response = run_external_call_sync(
                "nvidia-devstral-jsx",
                lambda: client.chat.completions.create(
                    model=settings.NV_MODEL_CODE,  # mistralai/devstral-2-123b-instruct-2512
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0,  # Deterministic output for production
                    top_p=0.95,
                    max_tokens=settings.NV_MAX_TOKENS_CODE,  # 8192
                    seed=42,  # Reproducible outputs
                ),
                timeout_seconds=float(settings.CODE_LLM_TIMEOUT_SECONDS),
            )

            modified_code = response.choices[0].message.content.strip()

            # Clean up markdown code blocks if Kimi added them
            modified_code = re.sub(r"^```tsx\s*\n", "", modified_code)
            modified_code = re.sub(r"^```typescript\s*\n", "", modified_code)
            modified_code = re.sub(r"^```\s*\n", "", modified_code)
            modified_code = re.sub(r"\n```\s*$", "", modified_code)

            # Validate the result
            if self._validate_jsx_code(modified_code, content):
                logger.info(f"Kimi successfully transformed JSX for {file_path}")
                return modified_code
            else:
                logger.warning(
                    f"Kimi response failed validation for {file_path}, keeping original"
                )
                return content

        except Exception as e:
            logger.error(f"Error in Kimi JSX transformation for {file_path}: {e}")
            return content

    def _build_transformation_instructions(self, fixes: List[Dict]) -> str:
        """Build detailed instructions for Kimi based on fix types"""
        instructions = []

        for fix in fixes:
            fix_type = fix.get("type")
            fix_value = fix.get("value")
            fix_value_dump = None
            if fix_value is not None:
                try:
                    fix_value_dump = json.dumps(fix_value, ensure_ascii=False)
                except Exception:
                    fix_value_dump = str(fix_value)

            if fix_type == "title":
                if fix_value_dump:
                    instructions.append(
                        f"- Set page title exactly to: {fix_value_dump}"
                    )
                else:
                    continue

            elif fix_type == "meta_description":
                if fix_value_dump:
                    instructions.append(
                        f"- Set meta description exactly to: {fix_value_dump}"
                    )
                else:
                    continue

            elif fix_type == "h1":
                if fix_value_dump:
                    instructions.append(
                        f"- Set the single <h1> exactly to: {fix_value_dump}"
                    )
                else:
                    continue

            elif fix_type == "structure":
                instructions.append(
                    "- Fix heading hierarchy: H1→H2→H3 (no skipping levels)"
                )

            elif fix_type == "schema":
                if isinstance(fix_value, dict) and fix_value_dump:
                    instructions.append(
                        f"""- Add Schema.org JSON-LD structured data using ONLY this org data (verbatim; do not invent): {fix_value_dump}
  * Use Article or WebPage schema type
  * Include only fields provided; omit missing optional fields
  * Wrap in <script type="application/ld+json"> tag
  * Use actual content from the page"""
                    )
                else:
                    continue

            elif fix_type == "alt_text":
                instructions.append(
                    "- Add descriptive alt text to ALL images (contextual, not generic)"
                )

            elif fix_type == "add_faq_section":
                if isinstance(fix_value, list) and fix_value_dump:
                    instructions.append(
                        f"""- Add FAQ section using ONLY these Q&A pairs (verbatim; do not invent): {fix_value_dump}
  * Use proper semantic HTML or components
  * Add FAQPage Schema.org if possible"""
                    )
                else:
                    continue

            elif fix_type == "add_author_metadata":
                if isinstance(fix_value, dict) and fix_value_dump:
                    instructions.append(
                        f"""- Add author information section using ONLY this data (verbatim; do not invent): {fix_value_dump}
  * Omit fields that are empty or missing
  * Place after main content"""
                    )
                else:
                    continue

            elif fix_type == "add_citations":
                instructions.append(
                    "- Add credible external citations/references (2-3 sources)"
                )

            elif fix_type == "add_statistics":
                instructions.append(
                    "- Include relevant statistics or data points (2-3 facts)"
                )

            elif fix_type == "restructure_intro":
                instructions.append(
                    "- Optimize intro paragraph: hook + value prop + CTA (150-200 words)"
                )

            elif fix_type == "add_lists_tables":
                instructions.append(
                    "- Convert dense text to lists or tables where appropriate"
                )

            elif fix_type == "add_case_study":
                instructions.append(
                    "- Add a mini case study or example (real-world application)"
                )

            elif fix_type == "content_enhancement":
                instructions.append("- Enhance content readability and depth")

        return "\n".join(instructions)

    def _validate_jsx_code(self, modified_code: str, original_code: str) -> bool:
        """Validate that modified code is valid JSX"""

        # Check 1: Must have imports
        if "import" not in modified_code:
            logger.warning("Validation failed: No imports found")
            return False

        # Check 2: Must have export or function
        if not (
            "export default" in modified_code
            or "export function" in modified_code
            or "function" in modified_code
        ):
            logger.warning("Validation failed: No component definition found")
            return False

        # Check 3: Must be reasonably sized (not truncated)
        if len(modified_code) < len(original_code) * 0.5:
            logger.warning(
                f"Validation failed: Code too short ({len(modified_code)} vs {len(original_code)} original)"
            )
            return False

        # Check 4: Must have balanced JSX tags (basic check)
        open_tags = len(re.findall(r"<\w+", modified_code))
        close_tags = len(re.findall(r"</\w+>", modified_code)) + len(
            re.findall(r"/>", modified_code)
        )

        if (
            abs(open_tags - close_tags) > 5
        ):  # Allow small variance for self-closing tags
            logger.warning(
                f"Validation failed: Unbalanced tags ({open_tags} open, {close_tags} close)"
            )
            return False

        logger.info("Validation passed")
        return True

    def _generate_metadata_with_kimi(
        self, context: Dict, audit_context: Dict = None
    ) -> Dict[str, str]:
        """Use Kimi AI to generate intelligent metadata"""

        audit_info = ""
        if audit_context:
            audit_info = f"""
AUDIT CONTEXT:
- Keywords: {', '.join(audit_context.get('keywords', [])[:5])}
- Topic: {audit_context.get('topic', 'Growth Hacking & SEO')}
"""

        prompt = f"""You are an SEO expert. Generate optimal metadata for a Next.js page.

File: {context['file_name']}
Content Preview: {context['preview'][:500]}
Headings: {', '.join(context['headings'][:3]) if context['headings'] else 'None'}
{audit_info}

Generate a JSON with:
- title: SEO-optimized title (50-60 chars, compelling, includes main keyword)
- description: Meta description (150-160 chars, actionable, includes CTA)

Respond ONLY with valid JSON, no markdown:
{{"title": "...", "description": "..."}}
"""

        try:
            # Usar Devstral para generación de metadata (relacionado a código)
            api_key = (
                settings.NV_API_KEY_CODE
                or settings.NVIDIA_API_KEY
                or settings.NV_API_KEY
            )
            client = OpenAI(api_key=api_key, base_url=settings.NV_BASE_URL)

            response = run_external_call_sync(
                "nvidia-devstral-metadata",
                lambda: client.chat.completions.create(
                    model=settings.NV_MODEL_CODE,  # Devstral para código
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0,
                    top_p=0.95,
                    max_tokens=300,
                    seed=42,
                ),
                timeout_seconds=float(settings.CODE_LLM_TIMEOUT_SECONDS),
            )

            response_content = response.choices[0].message.content.strip()
            response_content = re.sub(r"```json\s*|\s*```", "", response_content)

            metadata = json.loads(response_content)
            logger.info(f"Kimi generated metadata: {metadata.get('title', '')[:50]}...")
            return metadata

        except Exception as e:
            logger.error(f"Error generating metadata with Kimi: {e}")
            return {
                "title": (
                    context["headings"][0] if context["headings"] else "Page Title"
                ),
                "description": f"Learn about {context['headings'][0] if context['headings'] else 'this topic'}",
            }

    def _extract_file_context(self, content: str, file_path: str) -> Dict:
        """Extract context from file for AI generation"""
        headings = []
        soup = BeautifulSoup(content or "", "html.parser")
        for tag_name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            for heading_tag in soup.find_all(tag_name):
                text = heading_tag.get_text(" ", strip=True)
                if text and len(text) < 100:
                    headings.append(text)

        file_name = file_path.split("/")[-1].replace(".tsx", "").replace(".jsx", "")

        return {
            "file_name": file_name,
            "headings": headings,
            "preview": content[:1000],
            "has_jsx": "<" in content and ">" in content,
        }
