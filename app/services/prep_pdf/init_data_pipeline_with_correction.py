"""
PDF Init Data Pipeline with Misspell Correction
================================================
Same flow as init_data_pipeline.py but adds a misspell-correction step
after OCR formatting (before embedding the invisible text layer).

Flow:
  - NORMAL_TEXT      → copy as-is to target folder
  - CORRUPT_ENCODING → rasterize → OCR → format → correct → embed → copy
  - SCANNED_PDF      → rasterize → OCR → format → correct → embed → copy

Usage:
    python init_data_pipeline_with_correction.py
    (configure ROOT_PATH / TARGET_PATH / MISSPELL_* at the bottom of the file)
"""

import json
import logging
import os
import sys
import time
from pathlib import Path

# Allow running as a standalone script from any working directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from app.services.prep_pdf.init_data_pipeline import (
    classify_pdf,
    embed_hidden_text_to_temp,
    format_ocr_page,
    ocr_all_pages,
    remove_text_layer_to_temp,
    safe_copy,
)
from app.services.prep_pdf.misspell_service import correct_misspell

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ============================================================
# CONFIG — edit these to match your environment
# ============================================================

MISSPELL_API_KEY = "app-iIy7qQePuRTusfMiw0itpDio"
MISSPELL_BASE_URL = "http://localhost/v1"


# ============================================================
# SINGLE FILE ORCHESTRATOR (with correction)
# ============================================================

def process_single_pdf_with_correction(pdf_path: str, target_dir: str) -> dict:
    """
    Same as process_single_pdf but inserts a misspell-correction step
    after formatting and before embedding the invisible text layer.

    Returns a result record:
        {
            "file":   str,
            "type":   str | None,
            "status": "success" | "error",
            "output": str | None,
            "error":  str | None,
        }
    """
    result: dict = {
        "file":   pdf_path,
        "type":   None,
        "status": "error",
        "output": None,
        "error":  None,
    }
    temp_files: list[str] = []

    try:
        pdf_type       = classify_pdf(pdf_path)
        result["type"] = pdf_type
        log.info("  Type: %s", pdf_type)

        # ── NORMAL_TEXT ────────────────────────────────────────
        if pdf_type == "NORMAL_TEXT":
            dest             = safe_copy(pdf_path, target_dir)
            result["output"] = dest
            result["status"] = "success"

        # ── CORRUPT_ENCODING or SCANNED_PDF ───────────────────
        else:
            # Step 1 — rasterize every page to strip any text layer
            log.info("  [1/5] Rasterizing (removing any text layer) …")
            ocr_source = remove_text_layer_to_temp(pdf_path)
            temp_files.append(ocr_source)

            # Step 2 — OCR
            log.info("  [2/5] Running OCR on all pages …")
            raw_pages = ocr_all_pages(ocr_source)

            # Step 3 — Format
            log.info("  [3/5] Formatting OCR output …")
            formatted_pages = [format_ocr_page(p) for p in raw_pages]

            # Step 4 — Misspell correction (one API call per page)
            log.info("  [4/5] Correcting misspellings (%d page(s)) …", len(formatted_pages))
            corrected_pages: list[str] = []
            for idx, page_text in enumerate(formatted_pages, start=1):
                log.info("    Correcting page %d/%d …", idx, len(formatted_pages))
                corrected_pages.append(
                    correct_misspell(page_text, MISSPELL_API_KEY, MISSPELL_BASE_URL)
                )

            # Step 5 — Embed invisible text layer
            log.info("  [5/5] Embedding invisible text layer …")
            output_temp = embed_hidden_text_to_temp(ocr_source, corrected_pages)
            temp_files.append(output_temp)

            dest             = safe_copy(output_temp, target_dir, filename=os.path.basename(pdf_path))
            result["output"] = dest
            result["status"] = "success"

    except Exception as exc:
        result["error"]  = str(exc)
        result["status"] = "error"
        log.error("  ERROR: %s", exc)

    finally:
        for tmp in temp_files:
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:
                pass

    return result


# ============================================================
# MAIN RUNNER
# ============================================================

def main(root_path: str, target_path: str) -> None:
    """
    Walk root_path recursively, process every .pdf file with misspell correction,
    and write log.json to target_path.
    """
    os.makedirs(target_path, exist_ok=True)
    t0 = time.time()

    all_pdfs: list[str] = []
    for dirpath, _, filenames in os.walk(root_path):
        for fname in filenames:
            if fname.lower().endswith(".pdf"):
                all_pdfs.append(os.path.join(dirpath, fname))

    total = len(all_pdfs)
    log.info("Found %d PDF file(s) under '%s'", total, root_path)
    log.info("Output target: %s", target_path)
    log.info("Misspell correction: %s", MISSPELL_BASE_URL)
    log.info("=" * 60)

    records: list[dict] = []
    success_count = 0
    error_count   = 0
    log_path = os.path.join(target_path, "log.json")

    def _flush_log() -> None:
        elapsed_so_far = time.time() - t0
        log_data = {
            "summary": {
                "total":           total,
                "processed":       len(records),
                "remaining":       total - len(records),
                "success":         success_count,
                "failed":          error_count,
                "elapsed_seconds": round(elapsed_so_far, 2),
            },
            "files": records,
        }
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(log_data, f, ensure_ascii=False, indent=2)

    for idx, pdf_path in enumerate(all_pdfs, start=1):
        log.info("")
        log.info("[%d/%d] %s", idx, total, pdf_path)

        record = process_single_pdf_with_correction(pdf_path, target_path)
        records.append(record)

        if record["status"] == "success":
            success_count += 1
            log.info("  → %s", record["output"])
        else:
            error_count += 1

        _flush_log()
        log.info("  [log updated]")

    elapsed = time.time() - t0
    log.info("")
    log.info("=" * 60)
    log.info("Done.  Total: %d  |  Success: %d  |  Failed: %d", total, success_count, error_count)
    log.info("Elapsed: %.1f s", elapsed)
    log.info("Log: %s", log_path)


# ============================================================
# ENTRY POINT — configure paths here before running
# ============================================================

if __name__ == "__main__":
    ROOT_PATH   = r"D:\llm_dev\knowledge\data"
    TARGET_PATH = r"D:\llm_dev\knowledge\output_prepared_corrected"

    main(ROOT_PATH, TARGET_PATH)
