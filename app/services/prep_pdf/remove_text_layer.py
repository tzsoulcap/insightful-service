import fitz # PyMuPDF
import os

def remove_text_layer(original_pdf_path, target_folder):
    """
    ลบ text layer ออกจาก PDF โดยเหลือไว้แต่ภาพ
    original_pdf_path: ไฟล์ PDF ต้นฉบับ
    target_folder: โฟลเดอร์ที่เก็บไฟล์ PDF ที่ไม่มี text layer
    """
    if not os.path.exists(target_folder):
        os.makedirs(target_folder)
    output_path = os.path.join(target_folder, os.path.basename(original_pdf_path))
    doc = fitz.open(original_pdf_path)
    new_doc = fitz.open()
    for i, page in enumerate(doc):
        width, height = page.rect.width, page.rect.height
        # Rasterize หน้าเป็น pixmap → text จะกลายเป็น pixel ไม่ใช่ text อีกต่อไป
        pix = page.get_pixmap(dpi=300)
        new_page = new_doc.new_page(width=width, height=height)
        new_page.insert_image(new_page.rect, pixmap=pix)

    new_doc.save(output_path, garbage=4, deflate=True)
    new_doc.close()
    doc.close()
    print(f"✅ Removed text layer: {output_path}")

# --- ใช้งาน ---
file_with_text = r"no_ocr_file\(B 9-3) ATTG-S-SHE 181 ความปลอดภัยในการเปลี่ยน Cutting tool.pdf"
target_folder = r"output\cleaned_text_layer"
remove_text_layer(file_with_text, target_folder)