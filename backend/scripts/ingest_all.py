import os
import sys
import logging
from pathlib import Path

# Add backend directory to path so we can import core
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.ingestion import Ingestion

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("ingestion.log")
    ]
)
logger = logging.getLogger("ingest_all")

DATA_DIR = Path("backend/data")

def main():
    if not DATA_DIR.exists():
        logger.error(f"Data directory not found: {DATA_DIR}")
        return

    logger.info(f"Starting unified ingestion pipeline from: {DATA_DIR}")
    pipeline = Ingestion()
    
    pdf_count = 0
    xml_count = 0
    fail_count = 0

    # Recursive traversal
    for file_path in DATA_DIR.rglob("*"):
        if not file_path.is_file():
            continue

        try:
            if file_path.suffix.lower() == ".pdf":
                logger.info(f"Processing PDF: {file_path}")
                chunks = pipeline.ingest_pdf(str(file_path))
                if chunks > 0:
                    pdf_count += 1
                else:
                    fail_count += 1

            elif file_path.suffix.lower() == ".xml":
                logger.info(f"Processing XML: {file_path}")
                chunks = pipeline.ingest_xml(str(file_path))
                if chunks > 0:
                    xml_count += 1
                else:
                    fail_count += 1
            
            else:
                # logger.debug(f"Skipping unsupported file type: {file_path}")
                pass

        except Exception as e:
            logger.error(f"Unexpected error processing {file_path}: {e}")
            fail_count += 1

    logger.info("--- Ingestion Summary ---")
    logger.info(f"PDFs successfully ingested: {pdf_count}")
    logger.info(f"XMLs successfully ingested: {xml_count}")
    logger.info(f"Failed files: {fail_count}")
    logger.info("--------------------------")

if __name__ == "__main__":
    main()
