import json
import logging
import os
import sys

import pytest

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.create_pdf import create_comprehensive_pdf

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_audit_1_pdf():
    report_folder = r"C:\Users\Dell\auditor_geo\auditor_geo\reports\audit_1"

    print(f"Testing PDF generation for folder: {report_folder}")

    if not os.path.exists(report_folder):
        pytest.skip(f"Report folder not found: {report_folder}")

    # Check for expected files
    expected_files = [
        "keywords.json",
        "backlinks.json",
        "llm_visibility.json",
        "ag2_report.md",
    ]

    for f in expected_files:
        path = os.path.join(report_folder, f)
        if os.path.exists(path):
            size = os.path.getsize(path)
            print(f"Found {f} ({size} bytes)")
            try:
                if f.endswith(".json"):
                    with open(path, "r", encoding="utf-8") as jf:
                        data = json.load(jf)
                        print(
                            f"  - Valid JSON. Items: {len(data) if isinstance(data, list) else 'Object'}"
                        )
            except Exception as e:
                pytest.fail(f"Error reading {f}: {e}")
        else:
            print(f"Missing {f}")

    print("\nRunning create_comprehensive_pdf...")
    try:
        create_comprehensive_pdf(report_folder)
        print("Done.")
    except Exception as e:
        pytest.fail(f"Error during PDF generation: {e}")


if __name__ == "__main__":
    test_audit_1_pdf()
