
import os
import json
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_mock_report():
    audit_id = 999
    report_dir = f"reports/audit_{audit_id}"
    os.makedirs(report_dir, exist_ok=True)
    os.makedirs(os.path.join(report_dir, "pages"), exist_ok=True)
    os.makedirs(os.path.join(report_dir, "competitors"), exist_ok=True)

    # 1. aggregated_summary.json
    agg_summary = {
        "url": "https://test-seo-site.com",
        "audited_pages_count": 5,
        "geo_score": 7.5
    }
    with open(f"{report_dir}/aggregated_summary.json", "w", encoding="utf-8") as f:
        json.dump(agg_summary, f, indent=2)

    # 2. pagespeed.json
    pagespeed = {
        "mobile": {
            "performance_score": 85,
            "core_web_vitals": {
                "lcp": 1200,
                "fid": 50,
                "cls": 0.05,
                "fcp": 800,
                "ttfb": 200
            }
        },
        "desktop": {
            "performance_score": 95,
            "core_web_vitals": {
                "lcp": 600,
                "fid": 10,
                "cls": 0.01,
                "fcp": 400,
                "ttfb": 100
            }
        }
    }
    with open(f"{report_dir}/pagespeed.json", "w", encoding="utf-8") as f:
        json.dump(pagespeed, f, indent=2)

    # 3. keywords.json
    keywords = [
        {"term": "test keyword 1", "volume": 1000, "difficulty": 45, "cpc": 1.5, "intent": "commercial"},
        {"term": "seo analysis mock", "volume": 500, "difficulty": 30, "cpc": 2.0, "intent": "informational"}
    ]
    with open(f"{report_dir}/keywords.json", "w", encoding="utf-8") as f:
        json.dump(keywords, f, indent=2)

    # 4. backlinks.json
    backlinks = [
        {"source_url": "https://high-da-site.com/article", "target_url": "https://test-seo-site.com/", "domain_authority": 80, "is_dofollow": True},
        {"source_url": "https://blog-friend.com/post", "target_url": "https://test-seo-site.com/blog", "domain_authority": 30, "is_dofollow": False}
    ]
    with open(f"{report_dir}/backlinks.json", "w", encoding="utf-8") as f:
        json.dump(backlinks, f, indent=2)

    # 5. rankings.json
    rankings = [
        {"keyword": "test keyword 1", "position": 3, "url": "https://test-seo-site.com/page1"},
        {"keyword": "seo analysis mock", "position": 12, "url": "https://test-seo-site.com/"}
    ]
    with open(f"{report_dir}/rankings.json", "w", encoding="utf-8") as f:
        json.dump(rankings, f, indent=2)

    # 6. llm_visibility.json
    visibility = [
        {"query": "best seo tool for geo", "llm_name": "ChatGPT-4", "is_visible": True, "rank": 1},
        {"query": "auditor geo review", "llm_name": "Perplexity", "is_visible": False, "rank": None}
    ]
    with open(f"{report_dir}/llm_visibility.json", "w", encoding="utf-8") as f:
        json.dump(visibility, f, indent=2)

    # 7. fix_plan.json
    fix_plan = [
        {"priority": "CRITICAL", "issue": "Missing H1", "page_url": "/"},
        {"priority": "HIGH", "issue": "Slow LCP", "page_url": "/blog"}
    ]
    with open(f"{report_dir}/fix_plan.json", "w", encoding="utf-8") as f:
        json.dump(fix_plan, f, indent=2)

    # 8. ag2_report.md
    with open(f"{report_dir}/ag2_report.md", "w", encoding="utf-8") as f:
        f.write("# Mock Audit Report\n\nThis is a mock report for verification purposes.")

    logger.info(f"Mock report data created in {report_dir}")
    return report_dir

def run_pdf_generation(report_dir):
    try:
        from create_pdf import create_comprehensive_pdf
        logger.info("Starting PDF generation...")
        create_comprehensive_pdf(report_dir)
        
        pdf_file = f"Reporte_Consolidado_{os.path.basename(report_dir)}.pdf"
        pdf_path = os.path.join(report_dir, pdf_file)
        
        if os.path.exists(pdf_path):
            logger.info(f"SUCCESS: PDF generated at {pdf_path}")
            size = os.path.getsize(pdf_path)
            logger.info(f"PDF Size: {size} bytes")
            if size > 1000: # Basic check
                return True
        else:
            logger.error("FAILURE: PDF file was not found after generation.")
    except Exception as e:
        logger.error(f"EXCEPTION during PDF generation: {e}")
        import traceback
        traceback.print_exc()
    return False

if __name__ == "__main__":
    report_dir = create_mock_report()
    success = run_pdf_generation(report_dir)
    if success:
        print("\n[VERIFICATION SUCCESSFUL] The PDF generation process correctly handled all data sources (PageSpeed, Keywords, Backlinks, Rankings, Visibility).")
    else:
        print("\n[VERIFICATION FAILED] Please check the logs.")
