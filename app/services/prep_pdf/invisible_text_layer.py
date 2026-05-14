import fitz  # PyMuPDF
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import io
import os
import re

# ระบุชื่อฟอนต์และ Path ของไฟล์
font_name    = "ThaiSarabun"
font_path    = os.path.join(os.getcwd(), "Sarabun-Regular.ttf")
font_jp_name = "NotoSansJP"
font_jp_path = os.path.join(os.getcwd(), "NotoSansJP-Regular.ttf")

# Regex matching CJK runs (Japanese Hiragana, Katakana, Kanji, Korean)
_CJK_RE = re.compile(r'[\u3040-\u30ff\u31f0-\u31ff\u4e00-\u9faf\uac00-\ud7af]+')


def setup_fonts():
    """Register Sarabun (Thai/Latin) and NotoSansJP (CJK) with ReportLab."""
    active_font = "Helvetica"

    if os.path.exists(font_path):
        pdfmetrics.registerFont(TTFont(font_name, font_path))
        print(f"✅ Registered {font_name} from {font_path}")
        active_font = font_name
    else:
        print(f"❌ Font not found: {font_path}. Falling back to Helvetica.")

    if os.path.exists(font_jp_path):
        pdfmetrics.registerFont(TTFont(font_jp_name, font_jp_path))
        print(f"✅ Registered {font_jp_name} from {font_jp_path}")
    else:
        print(f"⚠️  JP font not found: {font_jp_path}. Japanese text may not render correctly.")

    return active_font


def _text_segments(text: str) -> list[tuple[str, str]]:
    """
    Split a string into (font_name, chunk) segments.
    CJK runs → font_jp_name (NotoSansJP)
    Everything else → active_font (Sarabun, covers Thai + Latin)
    """
    segments: list[tuple[str, str]] = []
    pos = 0
    for m in _CJK_RE.finditer(text):
        if m.start() > pos:
            segments.append((CURRENT_FONT, text[pos:m.start()]))
        segments.append((font_jp_name, m.group()))
        pos = m.end()
    if pos < len(text):
        segments.append((CURRENT_FONT, text[pos:]))
    return segments


# เรียกใช้งานก่อนสร้าง Canvas
CURRENT_FONT = setup_fonts()


def embed_hidden_text(original_pdf_path, ocr_text_list, output_path):
    """
    original_pdf_path: ไฟล์ PDF ต้นฉบับ
    ocr_text_list: รายชื่อข้อความ OCR แยกตามหน้า [page1_text, page2_text, ...]

    ข้อความจะถูก split เป็น segments ตาม character type:
    - Thai/Latin → Sarabun
    - CJK (ญี่ปุ่น/จีน/เกาหลี) → NotoSansJP
    ทั้งหมดเป็น invisible (render mode 3) แต่ยัง searchable ได้
    """
    doc = fitz.open(original_pdf_path)
    new_doc = fitz.open()

    for i, page in enumerate(doc):
        width, height = page.rect.width, page.rect.height

        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=(width, height))

        text_content = ocr_text_list[i] if i < len(ocr_text_list) else ""
        y = height - 20

        for line in text_content.split('\n'):
            if not line:
                y -= 9
                continue

            # Use PDFTextObject so setTextRenderMode is available
            text_obj = can.beginText(10, y)
            text_obj.setTextRenderMode(3)  # Mode 3 = Invisible but searchable
            for seg_font, chunk in _text_segments(line):
                text_obj.setFont(seg_font, 8)
                text_obj.textOut(chunk)  # advances cursor inline, no newline
            can.drawText(text_obj)

            y -= 9  # line height

        can.save()

        packet.seek(0)
        overlay_pdf = fitz.open("pdf", packet.read())

        new_page = new_doc.new_page(width=width, height=height)
        new_page.show_pdf_page(new_page.rect, doc, i)       # วางรูปหน้าเดิม
        new_page.show_pdf_page(new_page.rect, overlay_pdf, 0)  # วางข้อความทับ (ล่องหน)
        overlay_pdf.close()

    new_doc.save(output_path)
    new_doc.close()
    doc.close()