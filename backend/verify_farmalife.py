import logging
import os
import sys

# Load .env from parent directory before importing app modules
from dotenv import load_dotenv

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
env_path = os.path.join(parent_dir, ".env")
load_dotenv(env_path)

# Override DATABASE_URL to use SQLite for local testing
os.environ["DATABASE_URL"] = "sqlite:///./test_farmalife.db"

# Add the parent directory to sys.path to allow imports from app
sys.path.append(current_dir)

from app.core.config import settings
from app.core.database import SessionLocal, init_db
from app.models import Audit, AuditStatus
from app.workers.tasks import run_audit_task

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def verify_audit():
    logger.info("Starting manual verification for Farmalife...")

    # Ensure DB is initialized (if using sqlite/local)
    import asyncio

    from app import models  # Ensure models are loaded
    from app.core.database import init_db

    asyncio.run(init_db())

    db = SessionLocal()
    try:
        url = "https://www.farmalife.com.ar/"

        # Check if audit already exists to avoid clutter, or just create new one
        # For verification, a new one is better to test clean slate
        audit = Audit(url=url, domain="farmalife.com.ar", status=AuditStatus.PENDING)
        db.add(audit)
        db.commit()
        db.refresh(audit)

        logger.info(f"Created Audit ID: {audit.id} for {url}")

        # Run the task synchronously
        # We call the function directly, bypassing Celery broker
        try:
            run_audit_task(audit.id)
        except Exception as e:
            logger.error(f"Task failed with error: {e}")
            # Refresh audit to see if status was updated
            db.refresh(audit)
            logger.error(f"Audit Status: {audit.status}")
            logger.error(f"Error Message: {audit.error_message}")
            return

        # reload audit
        db.refresh(audit)

        logger.info(f"Audit Finished. Status: {audit.status}")

        if audit.status == AuditStatus.COMPLETED:
            logger.info("Audit Success!")

            # Verify Pages audited
            target_audit = audit.target_audit
            if target_audit:
                page_count = target_audit.get("audited_pages_count", 0)
                paths = target_audit.get("audited_page_paths", [])
                logger.info(f"Audited Pages Count: {page_count}")
                logger.info(f"First 10 Paths: {paths[:10]}")

                # Check for numeric paths
                numeric_paths = [p for p in paths if p.strip("/").isdigit()]
                if numeric_paths:
                    logger.warning(
                        f"Found numeric paths (should have been filtered): {numeric_paths}"
                    )
                else:
                    logger.info("No pure numeric paths found (Filter working).")

            # Verify LLM Report
            report = audit.report_markdown
            if report:
                logger.info(f"Report Length: {len(report)} chars")
                logger.info(f"Report Preview:\n{report[:500]}...")
            else:
                logger.error("Report is empty!")

        else:
            logger.error(f"Audit Failed. Status: {audit.status}")
            logger.error(f"Error: {audit.error_message}")

    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    verify_audit()
