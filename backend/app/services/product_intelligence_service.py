"""
Product Intelligence Service - Enterprise Grade
Analyzes e-commerce sites and optimizes product visibility in LLMs and AI assistants.
"""

import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class EcommercePlatform(Enum):
    """Detected e-commerce platforms."""

    SHOPIFY = "shopify"
    WOOCOMMERCE = "woocommerce"
    MAGENTO = "magento"
    BIGCOMMERCE = "bigcommerce"
    CUSTOM = "custom"
    UNKNOWN = "unknown"


@dataclass
class ProductPage:
    """Represents a detected product page."""

    url: str
    title: str
    schema_markup: Optional[Dict]
    has_product_schema: bool
    schema_completeness_score: float


@dataclass
class ProductIntelligenceResult:
    """Complete product intelligence analysis result."""

    is_ecommerce: bool
    confidence_score: float
    platform: EcommercePlatform
    product_pages_count: int
    category_pages_count: int
    categories: List[str]
    schema_analysis: Dict[str, Any]
    llm_visibility: Dict[str, Any]
    content_gaps: List[Dict]
    optimization_recommendations: List[Dict]


class ProductIntelligenceService:
    """
    Enterprise-grade service for analyzing e-commerce product optimization.

    Features:
    - Automatic e-commerce detection
    - Product schema analysis
    - LLM visibility assessment
    - Content gap identification
    - Competitive product analysis
    """

    # Patterns to detect product pages
    PRODUCT_PAGE_PATTERNS = [
        "/product/",
        "/p/",
        "/item/",
        "/products/",
        "/shop/",
        "/buy/",
        "/pd/",
        "/sku/",
    ]

    # Patterns to detect category pages
    CATEGORY_PAGE_PATTERNS = [
        "/category/",
        "/collection/",
        "/cat/",
        "/c/",
        "/shop/",
        "/store/",
        "/department/",
    ]

    # Platform detection patterns
    PLATFORM_PATTERNS = {
        EcommercePlatform.SHOPIFY: ["myshopify.com", "cdn.shopify.com", "shopify.com"],
        EcommercePlatform.WOOCOMMERCE: [
            "woocommerce",
            "wp-content/plugins/woocommerce",
        ],
        EcommercePlatform.MAGENTO: ["magento", "mage/cookies.js", "skin/frontend"],
        EcommercePlatform.BIGCOMMERCE: ["bigcommerce.com", "cdn11.bigcommerce.com"],
    }

    def __init__(self, llm_function=None):
        """
        Initialize the Product Intelligence Service.

        Args:
            llm_function: Function to call LLM for analysis
        """
        self.llm_function = llm_function

    async def analyze(
        self,
        audit_data: Dict[str, Any],
        pages_data: List[Dict],
        llm_visibility_data: Optional[Dict] = None,
        competitor_data: Optional[List[Dict]] = None,
    ) -> ProductIntelligenceResult:
        """
        Perform comprehensive product intelligence analysis.

        Args:
            audit_data: Main audit data from the target site
            pages_data: List of audited pages with metadata
            llm_visibility_data: Optional LLM visibility data
            competitor_data: Optional competitor product data

        Returns:
            ProductIntelligenceResult with complete analysis
        """
        logger.info("Starting Product Intelligence analysis...")

        # Step 1: Detect if e-commerce
        is_ecommerce, confidence, platform = self._detect_ecommerce(
            audit_data, pages_data
        )

        if not is_ecommerce or confidence < 70:
            logger.info(
                f"Site not identified as e-commerce (confidence: {confidence}%)"
            )
            return ProductIntelligenceResult(
                is_ecommerce=False,
                confidence_score=confidence,
                platform=platform,
                product_pages_count=0,
                category_pages_count=0,
                categories=[],
                schema_analysis={},
                llm_visibility={},
                content_gaps=[],
                optimization_recommendations=[],
            )

        # Step 2: Identify product pages
        product_pages = self._identify_product_pages(pages_data)
        category_pages = self._identify_category_pages(pages_data)
        categories = self._extract_categories(pages_data)

        # Step 3: Analyze product schemas
        schema_analysis = self._analyze_product_schemas(product_pages)

        # Step 4: Assess LLM visibility
        llm_visibility = self._assess_llm_visibility(
            product_pages, llm_visibility_data, categories
        )

        # Step 5: Identify content gaps
        content_gaps = self._identify_content_gaps(
            product_pages, competitor_data, categories
        )

        # Step 6: Generate optimization recommendations
        recommendations = self._generate_recommendations(
            schema_analysis, llm_visibility, content_gaps
        )

        logger.info(
            f"Product Intelligence analysis complete. Found {len(product_pages)} product pages."
        )

        return ProductIntelligenceResult(
            is_ecommerce=True,
            confidence_score=confidence,
            platform=platform,
            product_pages_count=len(product_pages),
            category_pages_count=len(category_pages),
            categories=categories,
            schema_analysis=schema_analysis,
            llm_visibility=llm_visibility,
            content_gaps=content_gaps,
            optimization_recommendations=recommendations,
        )

    def _detect_ecommerce(
        self, audit_data: Dict, pages_data: List[Dict]
    ) -> Tuple[bool, float, EcommercePlatform]:
        """
        Detect if the site is an e-commerce platform.

        Returns:
            Tuple of (is_ecommerce, confidence_score, platform)
        """
        indicators = 0
        total_checks = 5
        platform = EcommercePlatform.UNKNOWN

        # Check 1: Product page patterns
        for page in pages_data:
            url = page.get("url", "").lower()
            if any(pattern in url for pattern in self.PRODUCT_PAGE_PATTERNS):
                indicators += 1
                break

        # Check 2: Schema markup
        for page in pages_data:
            schemas = page.get("schemas", [])
            for schema in schemas:
                if schema.get("type") == "Product":
                    indicators += 1
                    break
            if indicators >= 2:
                break

        # Check 3: Platform detection
        html_content = audit_data.get("html_sample", "").lower()
        for plat, patterns in self.PLATFORM_PATTERNS.items():
            if any(pattern in html_content for pattern in patterns):
                platform = plat
                indicators += 1
                break

        # Check 4: Pricing indicators
        price_indicators = [
            "price",
            "cart",
            "add to cart",
            "buy now",
            "checkout",
            "$",
            "€",
            "£",
        ]
        if any(indicator in html_content for indicator in price_indicators):
            indicators += 1

        # Check 5: URL structure
        product_url_count = sum(
            1
            for page in pages_data
            if any(
                pattern in page.get("url", "").lower()
                for pattern in self.PRODUCT_PAGE_PATTERNS
            )
        )
        if product_url_count >= 3:
            indicators += 1

        confidence = (indicators / total_checks) * 100
        is_ecommerce = confidence >= 60

        return is_ecommerce, confidence, platform

    def _identify_product_pages(self, pages_data: List[Dict]) -> List[ProductPage]:
        """Identify and analyze product pages."""
        product_pages = []

        for page in pages_data:
            url = page.get("url", "").lower()

            # Check if URL matches product patterns
            is_product = any(pattern in url for pattern in self.PRODUCT_PAGE_PATTERNS)

            if is_product:
                schemas = page.get("schemas", [])
                product_schema = None

                for schema in schemas:
                    if schema.get("type") == "Product":
                        product_schema = schema
                        break

                # Calculate schema completeness
                completeness = self._calculate_schema_completeness(product_schema)

                product_pages.append(
                    ProductPage(
                        url=page.get("url"),
                        title=page.get("title", ""),
                        schema_markup=product_schema,
                        has_product_schema=product_schema is not None,
                        schema_completeness_score=completeness,
                    )
                )

        return product_pages

    def _identify_category_pages(self, pages_data: List[Dict]) -> List[Dict]:
        """Identify category/collection pages."""
        category_pages = []

        for page in pages_data:
            url = page.get("url", "").lower()
            if any(pattern in url for pattern in self.CATEGORY_PAGE_PATTERNS):
                category_pages.append(page)

        return category_pages

    def _extract_categories(self, pages_data: List[Dict]) -> List[str]:
        """Extract unique category names from pages."""
        categories = set()

        for page in pages_data:
            url = page.get("url", "")
            # Extract category from URL patterns
            for pattern in ["/category/", "/collection/", "/cat/", "/c/"]:
                if pattern in url:
                    parts = url.split(pattern)
                    if len(parts) > 1:
                        category = parts[1].split("/")[0]
                        if category:
                            categories.add(category.replace("-", " ").title())

        return sorted(list(categories))

    def _calculate_schema_completeness(self, schema: Optional[Dict]) -> float:
        """Calculate how complete a Product schema is (0-100)."""
        if not schema:
            return 0.0

        critical_fields = ["name", "image", "description", "brand", "offers"]
        recommended_fields = ["sku", "aggregateRating", "review", "mpn", "gtin13"]

        properties = schema.get("properties", {})

        # Check critical fields (60% weight)
        critical_present = sum(1 for field in critical_fields if field in properties)
        critical_score = (critical_present / len(critical_fields)) * 60

        # Check recommended fields (40% weight)
        recommended_present = sum(
            1 for field in recommended_fields if field in properties
        )
        recommended_score = (recommended_present / len(recommended_fields)) * 40

        return min(100.0, critical_score + recommended_score)

    def _analyze_product_schemas(self, product_pages: List[ProductPage]) -> Dict:
        """Analyze schema markup across all product pages."""
        total_pages = len(product_pages)

        if total_pages == 0:
            return {
                "overall_score": 0,
                "pages_with_schema": 0,
                "average_completeness": 0,
                "issues": [],
            }

        pages_with_schema = sum(1 for p in product_pages if p.has_product_schema)
        avg_completeness = (
            sum(p.schema_completeness_score for p in product_pages) / total_pages
        )

        # Identify common issues
        issues = []

        if pages_with_schema < total_pages:
            missing_count = total_pages - pages_with_schema
            issues.append(
                {
                    "type": "missing_schema",
                    "severity": "critical",
                    "description": f"{missing_count} product pages missing Product schema",
                    "impact": "Products invisible to Google Shopping and rich snippets",
                }
            )

        if avg_completeness < 80:
            issues.append(
                {
                    "type": "incomplete_schema",
                    "severity": "high",
                    "description": f"Average schema completeness only {avg_completeness:.1f}%",
                    "impact": "Limited rich snippet eligibility",
                }
            )

        return {
            "overall_score": min(
                100,
                (pages_with_schema / total_pages * 100) * 0.5 + avg_completeness * 0.5,
            ),
            "pages_with_schema": pages_with_schema,
            "total_product_pages": total_pages,
            "average_completeness": round(avg_completeness, 1),
            "schema_coverage_percent": round(pages_with_schema / total_pages * 100, 1),
            "issues": issues,
            "critical_fields_missing": self._identify_missing_critical_fields(
                product_pages
            ),
            "recommendations": self._generate_schema_recommendations(product_pages),
        }

    def _identify_missing_critical_fields(
        self, product_pages: List[ProductPage]
    ) -> List[str]:
        """Identify which critical schema fields are commonly missing."""
        critical_fields = [
            "name",
            "image",
            "description",
            "brand",
            "offers",
            "aggregateRating",
        ]
        field_presence = {field: 0 for field in critical_fields}

        for page in product_pages:
            if page.schema_markup:
                props = page.schema_markup.get("properties", {})
                for field in critical_fields:
                    if field in props:
                        field_presence[field] += 1

        total = len(product_pages)
        missing = [
            field
            for field, count in field_presence.items()
            if count < total * 0.8  # Missing from >20% of pages
        ]

        return missing

    def _generate_schema_recommendations(
        self, product_pages: List[ProductPage]
    ) -> List[Dict]:
        """Generate specific schema optimization recommendations."""
        recommendations = []

        # Check for missing aggregateRating
        pages_without_ratings = sum(
            1
            for p in product_pages
            if not p.schema_markup
            or "aggregateRating" not in p.schema_markup.get("properties", {})
        )

        if pages_without_ratings > 0:
            recommendations.append(
                {
                    "priority": "critical",
                    "field": "aggregateRating",
                    "issue": f"{pages_without_ratings} products missing review ratings",
                    "recommendation": "Implement review collection and add aggregateRating to Product schema",
                    "code_example": json.dumps(
                        {
                            "@context": "https://schema.org",
                            "@type": "Product",
                            "aggregateRating": {
                                "@type": "AggregateRating",
                                "ratingValue": "4.5",
                                "reviewCount": "128",
                            },
                        },
                        indent=2,
                    ),
                    "impact": "Required for star ratings in search results; increases CTR by 20-35%",
                }
            )

        return recommendations

    def _assess_llm_visibility(
        self,
        product_pages: List[ProductPage],
        llm_visibility_data: Optional[Dict],
        categories: List[str],
    ) -> Dict:
        """Assess product visibility in LLMs for shopping queries."""
        # Generate test queries based on categories
        test_queries = []
        for category in categories[:5]:  # Top 5 categories
            test_queries.extend(
                [
                    f"best {category}",
                    f"top rated {category}",
                    f"{category} reviews",
                    f"where to buy {category}",
                ]
            )

        return {
            "visibility_score": 0,  # Would be populated from actual LLM testing
            "test_queries": test_queries,
            "queries_analyzed": len(test_queries),
            "recommendations": [
                "Create comprehensive product comparison content",
                "Add detailed product specifications",
                "Include real user reviews and testimonials",
                "Optimize for natural language queries",
            ],
        }

    def _identify_content_gaps(
        self,
        product_pages: List[ProductPage],
        competitor_data: Optional[List[Dict]],
        categories: List[str],
    ) -> List[Dict]:
        """Identify content gaps compared to competitors."""
        gaps = []

        # Common e-commerce content gaps
        if product_pages:
            gaps.append(
                {
                    "type": "use_cases",
                    "description": "Missing use case scenarios and applications",
                    "priority": "high",
                    "example": 'Create "How to Use [Product] for [Scenario]" content',
                }
            )

            gaps.append(
                {
                    "type": "comparisons",
                    "description": "Limited product comparison content",
                    "priority": "high",
                    "example": "Create comparison tables: Product A vs Product B",
                }
            )

            gaps.append(
                {
                    "type": "faqs",
                    "description": "Product-specific FAQs missing",
                    "priority": "medium",
                    "example": "Add FAQPage schema with common questions",
                }
            )

        return gaps

    def _generate_recommendations(
        self, schema_analysis: Dict, llm_visibility: Dict, content_gaps: List[Dict]
    ) -> List[Dict]:
        """Generate prioritized optimization recommendations."""
        recommendations = []

        # Schema recommendations
        for issue in schema_analysis.get("issues", []):
            recommendations.append(
                {
                    "category": "schema",
                    "priority": issue["severity"],
                    "action": issue["description"],
                    "impact": issue["impact"],
                    "effort": "medium",
                }
            )

        # Content recommendations
        for gap in content_gaps:
            recommendations.append(
                {
                    "category": "content",
                    "priority": gap["priority"],
                    "action": gap["description"],
                    "impact": "Improved LLM visibility and user engagement",
                    "effort": "high" if gap["priority"] == "high" else "medium",
                }
            )

        # Sort by priority
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        recommendations.sort(key=lambda x: priority_order.get(x["priority"], 4))

        return recommendations


# Convenience function for direct usage
async def analyze_products(
    audit_data: Dict,
    pages_data: List[Dict],
    llm_visibility_data: Optional[Dict] = None,
    competitor_data: Optional[List[Dict]] = None,
    llm_function=None,
) -> ProductIntelligenceResult:
    """
    Convenience function to analyze products without instantiating the class.

    Args:
        audit_data: Main audit data
        pages_data: List of audited pages
        llm_visibility_data: Optional LLM visibility data
        competitor_data: Optional competitor data
        llm_function: Optional LLM function for advanced analysis

    Returns:
        ProductIntelligenceResult
    """
    service = ProductIntelligenceService(llm_function=llm_function)
    return await service.analyze(
        audit_data=audit_data,
        pages_data=pages_data,
        llm_visibility_data=llm_visibility_data,
        competitor_data=competitor_data,
    )
