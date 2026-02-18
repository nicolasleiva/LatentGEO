import logging
import os
import sys

import pytest

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.services.create_pdf import create_comprehensive_pdf

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_generate_pdf_from_files():
    report_folder = r"C:\Users\Dell\auditor_geo\auditor_geo\reports\audit_1"

    logger.info(f"Testing PDF generation using real files from: {report_folder}")

    if not os.path.exists(report_folder):
        pytest.skip(f"Report folder not found: {report_folder}")

    try:
        create_comprehensive_pdf(report_folder)
        logger.info("PDF generation completed successfully.")
    except Exception as e:
        pytest.fail(f"PDF generation failed: {e}")


if __name__ == "__main__":
    test_generate_pdf_from_files()
