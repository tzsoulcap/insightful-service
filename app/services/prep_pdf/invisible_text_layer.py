import fitz  # PyMuPDF
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import io
import os

# 1. ระบุชื่อฟอนต์และ Path ของไฟล์ (สมมติว่าไฟล์อยู่ในโฟลเดอร์เดียวกับโค้ด)
font_name = "ThaiSarabun"
font_path = os.path.join(os.getcwd(), "Sarabun-Regular.ttf")

def setup_thai_font():
    if os.path.exists(font_path):
        # 2. ลงทะเบียนฟอนต์เข้าสู่ระบบของ ReportLab
        pdfmetrics.registerFont(TTFont(font_name, font_path))
        print(f"✅ Success: Registered {font_name} from {font_path}")
        return font_name
    else:
        print(f"❌ Error: Font file not found at {font_path}")
        return "Helvetica" # Fallback

# เรียกใช้งานก่อนสร้าง Canvas
CURRENT_FONT = setup_thai_font()

def embed_hidden_text(original_pdf_path, ocr_text_list, output_path):
    """
    original_pdf_path: ไฟล์ PDF ต้นฉบับ
    ocr_text_list: รายชื่อข้อความ OCR แยกตามหน้า [page1_text, page2_text, ...]
    """
    

    doc = fitz.open(original_pdf_path)
    new_doc = fitz.open()

    for i, page in enumerate(doc):
        # 1. ดึงขนาดหน้าเดิม
        width, height = page.rect.width, page.rect.height
        
        # 2. สร้าง PDF เลเยอร์ข้อความชั่วคราวด้วย ReportLab
        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=(width, height))

        # วางข้อความ OCR ลงไป (ในที่นี้วางแบบปูพื้น)
        text_obj = can.beginText(10, height - 20)
        
        # --- เทคนิคสำคัญ: ตั้งค่าตัวอักษรให้โปร่งใส ---
        # แม้จะมองไม่เห็น แต่ Parser (Dify) จะยังอ่านได้
        text_obj.setTextRenderMode(3) # Mode 3 = Invisible
        
        
        text_obj.setFont(CURRENT_FONT, 8)
        
        # ใส่ข้อความลงไปทีละบรรทัด
        lines = ocr_text_list[i].split('\n')
        for line in lines:
            text_obj.textLine(line)
        
        can.drawText(text_obj)
        can.save()
        
        # 3. รวมเลเยอร์ข้อความเข้ากับหน้าเดิม
        packet.seek(0)
        overlay_pdf = fitz.open("pdf", packet.read())
        overlay_page = overlay_pdf[0]
        
        # รวมหน้าเดิมเข้ากับเลเยอร์ข้อความ
        new_page = new_doc.new_page(width=width, height=height)
        new_page.show_pdf_page(new_page.rect, doc, i) # วางรูปหน้าเดิม
        new_page.show_pdf_page(new_page.rect, overlay_pdf, 0) # วางข้อความทับ (แต่ล่องหน)
        
    new_doc.save(output_path)
    new_doc.close()
    doc.close()

# --- ใช้งาน ---
# ocr_results คือ list ของ Markdown ที่คุณได้จาก vLLM
markdown = 'AATG AISIN TAKAOKE THAILAND GROUP AT&amp;T INSURE AIFB Siam TEPAISIN TAKAOKE ASIA บริษัท ไอซิน ทาเกาโอะ เอเชีย จำกัดมาตรฐานการทำงาน (Standard)เรื่อง : มาตรฐาน Safety Cover ของส่วนที่มีอุณหภูมิสูง-ต่ำเอกสารของหน่วยงาน : เอกสารของหน่วยงานปลอดภัย AT-Aหน่วยงานความปลอดภัยและทุกหน่วยงานที่เกี่ยวข้องDoc No : ATTG-S-SHE-028 Issue Date : 9 Feb 15ผู้อนุมัติผู้ตรวจสอบผู้จดทำ หน่วยงานความปลอดภัย และทุกหน่วยงานที่เกี่ยวข้อง วัตถุประสงค์/หลักการ จุดที่อาจจะได้รับอันตรายจากพื้นผิวของเครื่องจักรที่มีอุณหภูมิสูงและต่ำ เป็นต้องติดตั้ง Cover ในกรณีที่ติดตั้งแบบ cover ทำได้ยากจำเป็นต้องติดตั้งเป็น safety fence หรือติดป้ายเตือน (อันตรายสูง/ต่ำ) เป็นต้น คำอธิบายพร้อมตัวอย่างประกอบ อุปกรณ์ อุปกรณ์โดยอยู่กับที่ ที่ผิวสัมผัสมีอุณหภูมิสูง (มากกว่า 70 C ขึ้นไป) อุณหภูมิต่ำ(ต่ำกว่า-10 C ) (ยกเว้นเสาหลอม Cupola และบ้าน) วัสดุ Body: ตะแกรงเหล็ก XS-31 33 หรือตาข่ายขนาดช่อง 50, แผ่นเหล็กมากว่า t=1.2mm ขึ้นไป สี Body: สีเหลือง (Munsell N 2, 7Y8 /12] หน้าต่าง : สีดำหรือสีเดียวกับเครื่องจักร (ตะแกรง) ป้องร่าง ติดตั้ง Safety cover ในจุดที่อุณหภูมิสูง อุณหภูมิต่ำ โดยให้มีช่องว่างระหว่าง Cover กับส่วนที่อุณหภูมิปกติไม่เกิน 10 mm แต่ช่องว่างจากพื้นไม่เกิน 200 mm วิธีการติดตั้ง ติดติดโดยใช้ Bolt ขนาด M6 จำนวนมากกว่า 2 อัน ในกรณีที่เป็นแบบสวม ให้ยึดส่วนที่สวมเข้าไปตามวิธีการข้างต้น หน้าต่าง ติดตั้งในส่วนที่จำเป็น เช่น valve กับ meter เป็นต้น ต้องยึดติดให้มั่นคง เมื่อเกิดแรงปะทะ / สั่นสะเทือนอย่างแรง จะไม่เปิดออก/เลื่อนหลุด หรือไม่ก็ทำเป็นแบบบานฟัน เปิด-ปิดได้ ตัวอย่างการติดตั้ง ภาพแสดงตัวอย่างการติดตั้ง Cover บนส่วนที่อุณหภูมิสูง โดยมีส่วนประกอบต่างๆ กำกับไว้ ได้แก่ "Cover" ที่เป็นแผ่นปิด, "ส่วนที่อุณหภูมิสูง" ที่เป็นพื้นที่ที่ติดตั้ง Cover, "ส่วนที่อุณหภูมิต่ำ" ที่อยู่ด้านล่าง, "ติดป้าย" และ "อันตรายอุณหภูมิสูง" ที่ระบุตำแหน่งของอันตราย มีข้อความกำกับว่า "ช่องว่างไม่เกิน 10mm", "ส่วนที่อุณหภูมิต่ำ", "อันตรายอุณหภูมิสูง", "ติดป้าย", "หน้าต่าง", "พื้น", "ไม่เกิน 200mm" และ "พื้น" ภาพนี้แสดงให้เห็นถึงการจัดวางและประเภทของอันตรายที่อาจเกิดขึ้นจากการติดตั้ง Cover อุบัติเหตุที่คาดการณ์หรือตัวอย่างที่เคยเกิด สมมุติว่า ขณะที่เดินอยู่ไม่ทันได้ระวัง มือหรือเท้าไปสัมผัสโดนส่วนที่มีอุณหภูมิสูง ทำให้โดนความร้อนลวกบ้างหรืออาจมีอุบัติเหตุที่อุณหภูมิต่ำมากอาจทำให้ผิวหนังหลุดร่วงได้ หมายเหตุ td'
embed_hidden_text(r"D:\setup_ipynb\need_ocr_file\(A 1-3) ATTG-S-SHE 028 มาตรฐาน safety cover ของส่วนที่อุณหภูมิสู.pdf", 
                  [markdown], 
                  r"output\(A 1-3) ATTG-S-SHE 028 มาตรฐาน safety cover ของส่วนที่อุณหภูมิสู_with_hidden_text.pdf")