"""
PDF Init Data Pipeline
======================
Batch-processes all PDF files under a root directory:
  - NORMAL_TEXT      → copy as-is to target folder
  - CORRUPT_ENCODING → rasterize (remove broken text layer) → OCR → invisible text layer → copy
  - SCANNED_PDF      → OCR → invisible text layer → copy

Results are written to target folder.  A log.json file tracks every file's outcome.

Usage:
    python init_data_pipeline.py
    (configure ROOT_PATH / TARGET_PATH at the bottom of the file)
"""

import io
import json
import logging
import os
import re
import shutil
import tempfile
import time
from io import StringIO
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF
fitz.TOOLS.mupdf_display_errors(False)  # suppress MuPDF stderr warnings (e.g. broken structure tree)
import pandas as pd
from bs4 import BeautifulSoup
from pypdf import PdfReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ============================================================
# CONFIG — loaded from app settings / .env
# ============================================================
from app.core.config import get_settings as _get_settings

_settings = _get_settings()

OCR_MODEL        = _settings.OCR_MODEL
OCR_BASE_URL     = _settings.OCR_BASE_URL
OCR_API_KEY      = _settings.OCR_API_KEY
TARGET_IMAGE_DIM = _settings.OCR_TARGET_IMAGE_DIM
FIGURE_LANGUAGE  = _settings.OCR_FIGURE_LANGUAGE
OCR_TASK_TYPE    = _settings.OCR_TASK_TYPE
MAX_TOKENS_CAP   = _settings.OCR_MAX_TOKENS_CAP   # vLLM server max; original model requests 16384

# Sarabun-Regular.ttf is expected at the project root
# (d:\GitHub\insightful-service\Sarabun-Regular.ttf)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
FONT_TTF_PATH = str(_PROJECT_ROOT / "Sarabun-Regular.ttf")
FONT_NAME     = "ThaiSarabun"
FONT_JP_TTF_PATH = str(_PROJECT_ROOT / "NotoSansJP-Regular.ttf")
FONT_JP_NAME     = "NotoSansJP"

# ============================================================
# Monkey-patch: cap max_tokens for 8k vLLM server
# ============================================================
import openai.resources.chat.completions as _oai_completions

_original_create = _oai_completions.Completions.create


def _patched_create(*args, **kwargs):
    if kwargs.get("max_tokens") == 16384:
        kwargs["max_tokens"] = MAX_TOKENS_CAP
    return _original_create(*args, **kwargs)


_oai_completions.Completions.create = _patched_create

# ============================================================
# Font setup for ReportLab (invisible text layer)
# ============================================================

def _setup_font() -> str:
    """Register Thai/Latin and Japanese fonts with ReportLab. Falls back to Helvetica if not found."""
    if os.path.exists(FONT_TTF_PATH):
        try:
            pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_TTF_PATH))
            log.info("Font registered: %s from %s", FONT_NAME, FONT_TTF_PATH)
        except Exception as exc:
            log.warning("Could not register font %s: %s. Falling back to Helvetica.", FONT_TTF_PATH, exc)
            return "Helvetica"
    else:
        log.warning("Font file not found: %s. Falling back to Helvetica.", FONT_TTF_PATH)
        return "Helvetica"

    if os.path.exists(FONT_JP_TTF_PATH):
        try:
            pdfmetrics.registerFont(TTFont(FONT_JP_NAME, FONT_JP_TTF_PATH))
            log.info("Font registered: %s from %s", FONT_JP_NAME, FONT_JP_TTF_PATH)
        except Exception as exc:
            log.warning("Could not register JP font %s: %s.", FONT_JP_TTF_PATH, exc)
    else:
        log.warning("JP font file not found: %s.", FONT_JP_TTF_PATH)

    return FONT_NAME


_CURRENT_FONT = _setup_font()

# ============================================================
# HELPER FUNCTIONS
# ============================================================

# ---------- 1. Classify PDF ----------------------------------

def classify_pdf(pdf_path: str) -> str:
    """
    Reads ALL pages to detect mixed PDFs (some pages have text, some are scanned).
    Returns:
        'NORMAL_TEXT'      — all pages have a readable text layer, minimal noise
        'CORRUPT_ENCODING' — text layer present on all pages but garbled characters
        'SCANNED_PDF'      — at least one page has no extractable text (image-only or mixed)
    """
    doc = fitz.open(pdf_path)
    page_texts = [page.get_text() for page in doc]
    doc.close()

    # If ANY page is empty → treat the whole document as SCANNED_PDF
    # (mixed PDFs with partial text layers must be fully rasterized before embed)
    if any(t.strip() == "" for t in page_texts):
        return "SCANNED_PDF"

    combined_text = "".join(page_texts)

    log.info("  Total chars extracted: %d", len(combined_text))

    if len(combined_text.strip()) < 500:
        return "SCANNED_PDF"

    safe_pattern = r'[\u0e00-\u0e7fa-zA-Z0-9\u3040-\u30ff\u4e00-\u9faf\s,.()\-/:\"\'\[\]]'
    safe_chars   = len(re.findall(safe_pattern, combined_text))
    total_chars  = len(combined_text)
    noise_ratio  = 1 - (safe_chars / total_chars) if total_chars > 0 else 1

    if noise_ratio > 0.02:
        return "CORRUPT_ENCODING"

    return "NORMAL_TEXT"


# ---------- 2. Remove text layer (rasterize) -----------------

def remove_text_layer_to_temp(pdf_path: str) -> str:
    """
    Rasterizes every page of the PDF to pixels (DPI=300), removing any text layer.
    Writes the result to a temporary file and returns its path.
    Caller is responsible for deleting the temp file when done.
    """
    doc = fitz.open(pdf_path)
    new_doc = fitz.open()

    for page in doc:
        width, height = page.rect.width, page.rect.height
        pix = page.get_pixmap(dpi=300)
        new_page = new_doc.new_page(width=width, height=height)
        new_page.insert_image(new_page.rect, pixmap=pix)

    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp_path = tmp.name
    tmp.close()

    new_doc.save(tmp_path, garbage=4, deflate=True)
    new_doc.close()
    doc.close()

    return tmp_path


# ---------- 3. OCR all pages ---------------------------------

def _ocr_page_via_image(pdf_path: str, page_num: int) -> str:
    """
    Fallback OCR path: render the page to a temporary PNG using PyMuPDF,
    then pass the image file to ocr_document.
    This bypasses Poppler (pdfinfo/pdftoppm) entirely, which fails on some PDFs.
    """
    from typhoon_ocr import ocr_document

    doc  = fitz.open(pdf_path)
    page = doc[page_num - 1]  # fitz is 0-indexed
    pix  = page.get_pixmap(dpi=150)
    doc.close()

    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp_path = tmp.name
    tmp.close()
    pix.save(tmp_path)

    try:
        text = ocr_document(
            pdf_or_image_path=tmp_path,
            page_num=1,  # images are always single-page
            model=OCR_MODEL,
            target_image_dim=TARGET_IMAGE_DIM,
            figure_language=FIGURE_LANGUAGE,
            task_type=OCR_TASK_TYPE,
            base_url=OCR_BASE_URL,
            api_key=OCR_API_KEY,
        )
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    return text or ""


def ocr_all_pages(pdf_path: str) -> list[str]:
    """
    Runs OCR on every page of the PDF via typhoon_ocr.
    Falls back to PyMuPDF-rendered PNG if Poppler fails on a page.
    Returns a list of raw OCR strings (one per page, in order).
    """
    from typhoon_ocr import ocr_document  # imported here to avoid triggering its side-effects at module level

    reader = PdfReader(pdf_path)
    total  = len(reader.pages)
    results: list[str] = []

    for page_num in range(1, total + 1):
        log.info("    OCR page %d/%d …", page_num, total)
        try:
            text = ocr_document(
                pdf_or_image_path=pdf_path,
                page_num=page_num,
                model=OCR_MODEL,
                target_image_dim=TARGET_IMAGE_DIM,
                figure_language=FIGURE_LANGUAGE,
                task_type=OCR_TASK_TYPE,
                base_url=OCR_BASE_URL,
                api_key=OCR_API_KEY,
            )
        except Exception as exc:
            log.warning("    Poppler failed on page %d (%s) — retrying via PyMuPDF image fallback …", page_num, exc)
            text = _ocr_page_via_image(pdf_path, page_num)
        results.append(text or "")

    return results


# ---------- 4. Format OCR output → clean Markdown ------------

def format_ocr_page(text: str) -> str:
    """
    Parses mixed Markdown + embedded HTML <table> output produced by task_type='v1.5'.
    Converts <table> blocks to Markdown tables; passes through plain text unchanged.
    """
    soup = BeautifulSoup(text, "html.parser")
    final_output: list[str] = []

    for element in soup.contents:
        if element.name == "table":
            try:
                df = pd.read_html(StringIO(str(element)))[0]
                df = df.dropna(axis=1, how="all").dropna(axis=0, how="all")
                final_output.append(f"\n{df.to_markdown(index=False)}\n")
            except Exception:
                # Fallback: plain text extraction from table
                raw = element.get_text(separator=" ").strip()
                if raw:
                    final_output.append(raw)
        elif element.name is not None:
            t = element.get_text().strip()
            if t:
                final_output.append(t)
        else:
            t = str(element).strip()
            if t:
                final_output.append(t)

    return "\n".join(final_output)


# ---------- 5. Embed invisible text layer --------------------

# Regex matching CJK characters (Japanese Hiragana, Katakana, Kanji, Korean)
_CJK_RE = re.compile(r'[\u3040-\u30ff\u31f0-\u31ff\u4e00-\u9faf\uac00-\ud7af]+')


def _text_segments(text: str) -> list[tuple[str, str]]:
    """
    Split a string into (font_name, chunk) segments.
    CJK runs → FONT_JP_NAME (NotoSansJP)
    Everything else → _CURRENT_FONT (Sarabun, covers Thai + Latin)
    """
    segments: list[tuple[str, str]] = []
    pos = 0
    for m in _CJK_RE.finditer(text):
        if m.start() > pos:
            segments.append((_CURRENT_FONT, text[pos:m.start()]))
        segments.append((FONT_JP_NAME, m.group()))
        pos = m.end()
    if pos < len(text):
        segments.append((_CURRENT_FONT, text[pos:]))
    return segments


def embed_hidden_text_to_temp(base_pdf_path: str, text_list: list[str]) -> str:
    """
    Overlays an invisible (render mode 3) text layer on each page of base_pdf_path.
    text_list[i] supplies the text for page i; pages beyond len(text_list) get no text.

    Text is split into font segments so Thai/Latin uses Sarabun and CJK uses NotoSansJP,
    enabling correct search across all three languages in a single page.

    Writes the result to a temp file and returns its path.
    Caller is responsible for deleting the temp file when done.
    """
    doc     = fitz.open(base_pdf_path)
    new_doc = fitz.open()

    for i, page in enumerate(doc):
        width, height = page.rect.width, page.rect.height

        # Build ReportLab overlay with invisible text
        packet = io.BytesIO()
        can    = canvas.Canvas(packet, pagesize=(width, height))
        text_content = text_list[i] if i < len(text_list) else ""

        y = height - 20
        for line in text_content.split("\n"):
            if not line:
                y -= 9   # blank line advance
                continue

            # Use PDFTextObject so setTextRenderMode is available
            text_obj = can.beginText(10, y)
            text_obj.setTextRenderMode(3)  # Mode 3 = invisible but searchable
            for seg_font, chunk in _text_segments(line):
                text_obj.setFont(seg_font, 8)
                text_obj.textOut(chunk)  # advances cursor inline, no newline
            can.drawText(text_obj)

            y -= 9  # line height for font size 8

        can.save()

        # Merge original page visual + overlay
        packet.seek(0)
        overlay_pdf  = fitz.open("pdf", packet.read())
        new_page     = new_doc.new_page(width=width, height=height)
        new_page.show_pdf_page(new_page.rect, doc, i)          # original visual
        new_page.show_pdf_page(new_page.rect, overlay_pdf, 0)  # invisible text on top
        overlay_pdf.close()

    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp_path = tmp.name
    tmp.close()

    new_doc.save(tmp_path)
    new_doc.close()
    doc.close()

    return tmp_path


# ---------- 6. Safe copy with collision handling -------------

def safe_copy(src: str, target_dir: str, filename: str | None = None) -> str:
    """
    Copies src into target_dir using `filename` as the destination name.
    If filename is None, the basename of src is used.
    If a file with the same name already exists, appends _copy, _copy2, _copy3 … until unique.
    Returns the final destination path.
    """
    os.makedirs(target_dir, exist_ok=True)
    stem, ext = os.path.splitext(filename if filename else os.path.basename(src))
    dest      = os.path.join(target_dir, f"{stem}{ext}")

    counter = 0
    while os.path.exists(dest):
        counter += 1
        suffix = "_copy" if counter == 1 else f"_copy{counter}"
        dest   = os.path.join(target_dir, f"{stem}{suffix}{ext}")

    shutil.copy2(src, dest)
    return dest


# ============================================================
# SINGLE FILE ORCHESTRATOR
# ============================================================

def process_single_pdf(pdf_path: str, target_dir: str) -> dict:
    """
    Processes one PDF file end-to-end based on its classification.

    Returns a result record:
        {
            "file":   str,                  # absolute input path
            "type":   str | None,           # NORMAL_TEXT / CORRUPT_ENCODING / SCANNED_PDF
            "status": "success" | "error",
            "output": str | None,           # destination path on success
            "error":  str | None,           # error message on failure
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
        pdf_type        = classify_pdf(pdf_path)
        result["type"]  = pdf_type
        log.info("  Type: %s", pdf_type)

        # ── NORMAL_TEXT ────────────────────────────────────────
        if pdf_type == "NORMAL_TEXT":
            dest             = safe_copy(pdf_path, target_dir)
            result["output"] = dest
            result["status"] = "success"

        # ── CORRUPT_ENCODING or SCANNED_PDF ───────────────────
        else:
            # Step 1 — rasterize every page to strip any text layer
            # CORRUPT: removes garbled text; SCANNED: removes partial text on mixed-page PDFs
            log.info("  [1/4] Rasterizing (removing any text layer) …")
            ocr_source = remove_text_layer_to_temp(pdf_path)
            temp_files.append(ocr_source)

            # Step 2 — OCR
            log.info("  [2/4] Running OCR on all pages …")
            raw_pages = ocr_all_pages(ocr_source)

            # Step 3 — Format
            log.info("  [3/4] Formatting OCR output …")
            formatted_pages = [format_ocr_page(p) for p in raw_pages]

            # Step 4 — Embed invisible text layer
            # For both types embed onto the rasterized/original image PDF
            # (visually clean pixels; original layout preserved)
            log.info("  [4/4] Embedding invisible text layer …")
            output_temp = embed_hidden_text_to_temp(ocr_source, formatted_pages)
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
    Walk root_path recursively, process every .pdf file, and write log.json to target_path.
    """
    os.makedirs(target_path, exist_ok=True)
    t0 = time.time()

    # Collect all PDF paths
    all_pdfs: list[str] = []
    for dirpath, _, filenames in os.walk(root_path):
        for fname in filenames:
            if fname.lower().endswith(".pdf"):
                all_pdfs.append(os.path.join(dirpath, fname))

    total = len(all_pdfs)
    log.info("Found %d PDF file(s) under '%s'", total, root_path)
    log.info("Output target: %s", target_path)
    log.info("=" * 60)

    records: list[dict] = []
    success_count = 0
    error_count   = 0
    log_path = os.path.join(target_path, "log.json")

    def _flush_log() -> None:
        """Write current state of log.json — called after every file."""
        elapsed_so_far = time.time() - t0
        log_data = {
            "summary": {
                "total":              total,
                "processed":          len(records),
                "remaining":          total - len(records),
                "success":            success_count,
                "failed":             error_count,
                "elapsed_seconds":    round(elapsed_so_far, 2),
            },
            "files": records,
        }
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(log_data, f, ensure_ascii=False, indent=2)

    for idx, pdf_path in enumerate(all_pdfs, start=1):
        log.info("")
        log.info("[%d/%d] %s", idx, total, pdf_path)

        record = process_single_pdf(pdf_path, target_path)
        records.append(record)

        if record["status"] == "success":
            success_count += 1
            log.info("  → %s", record["output"])
        else:
            error_count += 1

        # Flush log after every file so progress is always persisted
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
    ROOT_PATH   = r"D:\llm_dev\knowledge\ATTG STD\ATTG std refer Thai legal"
    TARGET_PATH = r"D:\llm_dev\knowledge\ATTG STD Prep"

    main(ROOT_PATH, TARGET_PATH)
