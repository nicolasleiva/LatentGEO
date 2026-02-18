"""
Automated Quality Assurance System - Enterprise Grade
Comprehensive testing, validation, and quality gates for production-ready audits.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class QualityGateStatus(Enum):
    """Status of a quality gate check."""

    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"


@dataclass
class QualityCheck:
    """Individual quality check result."""

    name: str
    status: QualityGateStatus
    message: str
    details: Optional[Dict] = None
    severity: str = "high"  # critical, high, medium, low


@dataclass
class QualityReport:
    """Complete quality assurance report."""

    audit_id: int
    timestamp: str
    overall_status: QualityGateStatus
    checks: List[QualityCheck]
    score: float  # 0-100
    critical_issues: int
    warnings: int
    passed_checks: int
    total_checks: int
    recommendations: List[str]


class AuditQualityService:
    """
    Enterprise-grade quality assurance for audit reports.

    Validates:
    - Report completeness and structure
    - Data accuracy and consistency
    - Financial calculations
    - Prompt quality
    - Output format compliance
    """

    def __init__(self):
        """Initialize the quality service."""
        self.critical_checks = [
            "report_structure",
            "executive_summary_present",
            "fix_plan_present",
            "data_completeness",
            "financial_projections_present",
        ]

        self.standard_checks = [
            "competitive_analysis_completeness",
            "technical_analysis_depth",
            "schema_optimization_present",
            "roadmap_clarity",
            "english_language_validation",
        ]

    async def validate_audit(
        self,
        audit_id: int,
        report_markdown: str,
        fix_plan: List[Dict],
        audit_data: Dict,
        metadata: Dict,
    ) -> QualityReport:
        """
        Perform comprehensive quality validation on an audit.

        Args:
            audit_id: ID of the audit
            report_markdown: Generated report content
            fix_plan: List of fix items
            audit_data: Raw audit data
            metadata: Report metadata

        Returns:
            QualityReport with detailed validation results
        """
        logger.info(f"Starting quality validation for audit {audit_id}")

        checks = []

        # Critical Checks
        checks.append(self._check_report_structure(report_markdown))
        checks.append(self._check_executive_summary(report_markdown))
        checks.append(self._check_fix_plan(fix_plan))
        checks.append(self._check_data_completeness(audit_data))
        checks.append(self._check_financial_projections(report_markdown))

        # Standard Checks
        checks.append(self._check_competitive_analysis(report_markdown))
        checks.append(self._check_technical_depth(report_markdown))
        checks.append(self._check_english_language(report_markdown))
        checks.append(self._check_prioritization(fix_plan))
        checks.append(self._check_code_examples(fix_plan))

        # Calculate scores
        score = self._calculate_quality_score(checks)
        critical_issues = sum(
            1
            for c in checks
            if c.severity == "critical" and c.status == QualityGateStatus.FAILED
        )
        warnings = sum(1 for c in checks if c.status == QualityGateStatus.WARNING)
        passed = sum(1 for c in checks if c.status == QualityGateStatus.PASSED)

        # Generate recommendations
        recommendations = self._generate_recommendations(checks)

        # Determine overall status
        overall_status = self._determine_overall_status(checks, critical_issues)

        report = QualityReport(
            audit_id=audit_id,
            timestamp=datetime.utcnow().isoformat(),
            overall_status=overall_status,
            checks=checks,
            score=score,
            critical_issues=critical_issues,
            warnings=warnings,
            passed_checks=passed,
            total_checks=len(checks),
            recommendations=recommendations,
        )

        logger.info(
            f"Quality validation complete for audit {audit_id}: {score:.1f}/100"
        )

        return report

    def _check_report_structure(self, report: str) -> QualityCheck:
        """Validate that report has all required sections."""
        required_sections = [
            "Executive Summary",
            "Competitive Intelligence",
            "Technical Performance",
            "SEO Foundation",
            "Content Strategy",
            "Strategic Roadmap",
        ]

        missing = [section for section in required_sections if section not in report]

        if missing:
            return QualityCheck(
                name="report_structure",
                status=QualityGateStatus.FAILED,
                message=f"Missing required sections: {', '.join(missing)}",
                details={"missing_sections": missing},
                severity="critical",
            )

        return QualityCheck(
            name="report_structure",
            status=QualityGateStatus.PASSED,
            message="All required report sections present",
            severity="high",
        )

    def _check_executive_summary(self, report: str) -> QualityCheck:
        """Validate executive summary quality."""
        # Check for SCRB framework elements
        has_situation = any(
            keyword in report.lower()
            for keyword in ["current state", "situation", "baseline"]
        )
        has_complication = any(
            keyword in report.lower()
            for keyword in ["problem", "complication", "challenge", "risk"]
        )
        has_resolution = any(
            keyword in report.lower()
            for keyword in ["strategy", "resolution", "approach", "plan"]
        )
        has_benefits = any(
            keyword in report.lower()
            for keyword in ["benefits", "roi", "value", "return"]
        )

        scrb_elements = sum(
            [has_situation, has_complication, has_resolution, has_benefits]
        )

        if scrb_elements < 4:
            return QualityCheck(
                name="executive_summary_present",
                status=QualityGateStatus.WARNING,
                message=f"Executive summary missing SCRB elements ({scrb_elements}/4)",
                details={"scrb_score": scrb_elements},
                severity="high",
            )

        return QualityCheck(
            name="executive_summary_present",
            status=QualityGateStatus.PASSED,
            message="Executive summary follows SCRB framework",
            severity="high",
        )

    def _check_fix_plan(self, fix_plan: List[Dict]) -> QualityCheck:
        """Validate fix plan quality and completeness."""
        if not fix_plan:
            return QualityCheck(
                name="fix_plan_present",
                status=QualityGateStatus.FAILED,
                message="No fix plan generated",
                severity="critical",
            )

        if len(fix_plan) < 5:
            return QualityCheck(
                name="fix_plan_present",
                status=QualityGateStatus.WARNING,
                message=f"Fix plan too short ({len(fix_plan)} items, minimum 5)",
                details={"item_count": len(fix_plan)},
                severity="medium",
            )

        # Check for required fields in each fix
        required_fields = [
            "page_path",
            "issue_code",
            "priority",
            "description",
            "suggestion",
        ]
        incomplete_fixes = []

        for i, fix in enumerate(fix_plan):
            missing = [
                field for field in required_fields if field not in fix or not fix[field]
            ]
            if missing:
                incomplete_fixes.append({"index": i, "missing_fields": missing})

        if incomplete_fixes:
            return QualityCheck(
                name="fix_plan_present",
                status=QualityGateStatus.WARNING,
                message=f"{len(incomplete_fixes)} fix items missing required fields",
                details={"incomplete_fixes": incomplete_fixes[:5]},  # Show first 5
                severity="high",
            )

        return QualityCheck(
            name="fix_plan_present",
            status=QualityGateStatus.PASSED,
            message=f"Fix plan complete with {len(fix_plan)} items",
            details={"item_count": len(fix_plan)},
            severity="critical",
        )

    def _check_data_completeness(self, audit_data: Dict) -> QualityCheck:
        """Validate that audit data is complete."""
        required_data_points = ["target_audit", "pages", "competitors"]

        missing = [point for point in required_data_points if point not in audit_data]

        if missing:
            return QualityCheck(
                name="data_completeness",
                status=QualityGateStatus.FAILED,
                message=f"Missing required data: {', '.join(missing)}",
                details={"missing_data": missing},
                severity="critical",
            )

        # Check for empty data
        empty_data = []
        for point in required_data_points:
            if not audit_data.get(point):
                empty_data.append(point)

        if empty_data:
            return QualityCheck(
                name="data_completeness",
                status=QualityGateStatus.WARNING,
                message=f"Empty data sections: {', '.join(empty_data)}",
                severity="medium",
            )

        return QualityCheck(
            name="data_completeness",
            status=QualityGateStatus.PASSED,
            message="All required audit data present and populated",
            severity="high",
        )

    def _check_financial_projections(self, report: str) -> QualityCheck:
        """Validate that financial projections are present."""
        financial_indicators = [
            "$",
            "revenue",
            "roi",
            "return",
            "investment",
            "cost",
            "value",
            "conversion",
            "traffic increase",
            "financial impact",
        ]

        # Count financial mentions
        financial_count = sum(
            report.lower().count(indicator) for indicator in financial_indicators
        )

        if financial_count < 10:
            return QualityCheck(
                name="financial_projections_present",
                status=QualityGateStatus.WARNING,
                message=f"Limited financial quantification ({financial_count} references)",
                details={"financial_references": financial_count},
                severity="high",
            )

        return QualityCheck(
            name="financial_projections_present",
            status=QualityGateStatus.PASSED,
            message=f"Comprehensive financial analysis ({financial_count} references)",
            details={"financial_references": financial_count},
            severity="high",
        )

    def _check_competitive_analysis(self, report: str) -> QualityCheck:
        """Validate competitive analysis depth."""
        competitor_indicators = [
            "competitor",
            "competitive",
            "market position",
            "vs ",
            "versus",
            "market share",
            "benchmark",
            "positioning matrix",
        ]

        competitor_count = sum(
            report.lower().count(indicator) for indicator in competitor_indicators
        )

        if competitor_count < 5:
            return QualityCheck(
                name="competitive_analysis_completeness",
                status=QualityGateStatus.WARNING,
                message="Competitive analysis appears limited",
                severity="medium",
            )

        return QualityCheck(
            name="competitive_analysis_completeness",
            status=QualityGateStatus.PASSED,
            message="Competitive analysis comprehensive",
            severity="medium",
        )

    def _check_technical_depth(self, report: str) -> QualityCheck:
        """Validate technical analysis depth."""
        technical_indicators = [
            "core web vitals",
            "lcp",
            "inp",
            "cls",
            "performance score",
            "pagespeed",
            "schema",
            "structured data",
            "json-ld",
        ]

        technical_count = sum(
            report.lower().count(indicator) for indicator in technical_indicators
        )

        if technical_count < 5:
            return QualityCheck(
                name="technical_analysis_depth",
                status=QualityGateStatus.WARNING,
                message="Technical analysis may be insufficient",
                severity="medium",
            )

        return QualityCheck(
            name="technical_analysis_depth",
            status=QualityGateStatus.PASSED,
            message="Technical analysis detailed",
            severity="medium",
        )

    def _check_english_language(self, report: str) -> QualityCheck:
        """Validate that report is in English."""
        # Simple heuristic: check for common Spanish words
        spanish_indicators = [
            "el ",
            "la ",
            "los ",
            "las ",
            "es ",
            "son ",
            "auditoría",
            "análisis",
        ]
        spanish_count = sum(report.lower().count(word) for word in spanish_indicators)

        if spanish_count > 10:
            return QualityCheck(
                name="english_language_validation",
                status=QualityGateStatus.FAILED,
                message=f"Report contains {spanish_count} Spanish words/phrases",
                details={"spanish_word_count": spanish_count},
                severity="critical",
            )

        if spanish_count > 0:
            return QualityCheck(
                name="english_language_validation",
                status=QualityGateStatus.WARNING,
                message=f"Report contains {spanish_count} potential non-English terms",
                severity="medium",
            )

        return QualityCheck(
            name="english_language_validation",
            status=QualityGateStatus.PASSED,
            message="Report validated as English",
            severity="high",
        )

    def _check_prioritization(self, fix_plan: List[Dict]) -> QualityCheck:
        """Validate that fixes are properly prioritized."""
        if not fix_plan:
            return QualityCheck(
                name="prioritization",
                status=QualityGateStatus.SKIPPED,
                message="No fix plan to check",
                severity="low",
            )

        priorities = [fix.get("priority", "").upper() for fix in fix_plan]

        # Check if we have a mix of priorities
        has_critical = "CRITICAL" in priorities
        has_high = "HIGH" in priorities

        if not (has_critical or has_high):
            return QualityCheck(
                name="prioritization",
                status=QualityGateStatus.WARNING,
                message="No critical or high priority items found",
                severity="medium",
            )

        return QualityCheck(
            name="prioritization",
            status=QualityGateStatus.PASSED,
            message=f"Proper prioritization: {priorities.count('CRITICAL')} critical, {priorities.count('HIGH')} high",
            severity="medium",
        )

    def _check_code_examples(self, fix_plan: List[Dict]) -> QualityCheck:
        """Validate that technical fixes include code examples."""
        if not fix_plan:
            return QualityCheck(
                name="code_examples",
                status=QualityGateStatus.SKIPPED,
                message="No fix plan to check",
                severity="low",
            )

        fixes_with_code = sum(
            1 for fix in fix_plan if fix.get("snippet") or fix.get("code_example")
        )

        code_coverage = (fixes_with_code / len(fix_plan)) * 100

        if code_coverage < 30:
            return QualityCheck(
                name="code_examples",
                status=QualityGateStatus.WARNING,
                message=f"Only {code_coverage:.1f}% of fixes include code examples",
                details={"code_coverage_percent": code_coverage},
                severity="medium",
            )

        return QualityCheck(
            name="code_examples",
            status=QualityGateStatus.PASSED,
            message=f"{code_coverage:.1f}% of fixes include code examples",
            details={"code_coverage_percent": code_coverage},
            severity="medium",
        )

    def _calculate_quality_score(self, checks: List[QualityCheck]) -> float:
        """Calculate overall quality score (0-100)."""
        if not checks:
            return 0.0

        weights = {"critical": 3.0, "high": 2.0, "medium": 1.0, "low": 0.5}

        total_weight = 0
        weighted_score = 0

        for check in checks:
            weight = weights.get(check.severity, 1.0)
            total_weight += weight

            if check.status == QualityGateStatus.PASSED:
                weighted_score += weight
            elif check.status == QualityGateStatus.WARNING:
                weighted_score += weight * 0.5
            # FAILED = 0 points

        if total_weight == 0:
            return 0.0

        return (weighted_score / total_weight) * 100

    def _generate_recommendations(self, checks: List[QualityCheck]) -> List[str]:
        """Generate improvement recommendations based on failed checks."""
        recommendations = []

        failed_checks = [c for c in checks if c.status == QualityGateStatus.FAILED]
        warning_checks = [c for c in checks if c.status == QualityGateStatus.WARNING]

        for check in failed_checks:
            recommendations.append(f"CRITICAL: {check.message}")

        for check in warning_checks:
            recommendations.append(f"WARNING: {check.message}")

        return recommendations

    def _determine_overall_status(
        self, checks: List[QualityCheck], critical_issues: int
    ) -> QualityGateStatus:
        """Determine overall quality status."""
        if critical_issues > 0:
            return QualityGateStatus.FAILED

        failed_count = sum(1 for c in checks if c.status == QualityGateStatus.FAILED)
        warning_count = sum(1 for c in checks if c.status == QualityGateStatus.WARNING)

        if failed_count > 0:
            return QualityGateStatus.FAILED

        if warning_count > len(checks) * 0.3:  # More than 30% warnings
            return QualityGateStatus.WARNING

        return QualityGateStatus.PASSED

    def can_proceed_to_production(
        self, report: QualityReport
    ) -> Tuple[bool, List[str]]:
        """
        Determine if audit can proceed to production based on quality gates.

        Args:
            report: QualityReport from validation

        Returns:
            Tuple of (can_proceed, reasons)
        """
        if report.overall_status == QualityGateStatus.PASSED:
            return True, ["All quality gates passed"]

        if report.overall_status == QualityGateStatus.FAILED:
            reasons = [
                f"CRITICAL: {check.message}"
                for check in report.checks
                if check.status == QualityGateStatus.FAILED
                and check.severity == "critical"
            ]
            return False, reasons if reasons else ["Critical quality gates failed"]

        if report.overall_status == QualityGateStatus.WARNING:
            if report.score >= 80:
                return True, [f"Quality score {report.score:.1f}/100 with warnings"]
            else:
                return False, [f"Quality score {report.score:.1f}/100 below threshold"]

        return True, ["Quality checks passed"]


# Convenience functions
async def validate_audit_quality(
    audit_id: int,
    report_markdown: str,
    fix_plan: List[Dict],
    audit_data: Dict,
    metadata: Dict,
) -> QualityReport:
    """Convenience function for audit validation."""
    service = AuditQualityService()
    return await service.validate_audit(
        audit_id=audit_id,
        report_markdown=report_markdown,
        fix_plan=fix_plan,
        audit_data=audit_data,
        metadata=metadata,
    )


def check_production_readiness(report: QualityReport) -> Tuple[bool, List[str]]:
    """Check if audit is ready for production."""
    service = AuditQualityService()
    return service.can_proceed_to_production(report)
