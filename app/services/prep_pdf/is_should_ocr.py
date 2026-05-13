import re
import fitz  # PyMuPDF

def peek_unsafe_characters(text):
    # Safe Pattern เดิมที่เราคุยกัน (ไทย, อังกฤษ, ญี่ปุ่น, พื้นฐาน)
    safe_pattern = r'[\u0e00-\u0e7fa-zA-Z0-9\u3040-\u30ff\u4e00-\u9faf\s,.()\-/:\"\'\[\]]'
    
    # ใช้ [^...] เพื่อหาตัวที่ "ไม่อยู่ใน" Safe Pattern
    unsafe_chars = re.findall(f'[^{safe_pattern[1:-1]}]', text)
    
    # กรองเอาเฉพาะตัวที่ไม่ซ้ำกัน (Unique) เพื่อให้ดูง่าย
    unique_unsafe = sorted(list(set(unsafe_chars)))
    
    return unique_unsafe



def classify_multilingual_pdf(pdf_path, sample_pages=2):
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc[:sample_pages]:
        text += page.get_text()

    # print(f"พบอักขระแปลกปลอม: {peek_unsafe_characters(text)}")
    
    if len(text.strip()) < 50:
        return "SCANNED_PDF"

    # 1. กำหนด Regex สำหรับ "อักขระที่ควรจะมี" (Safe Zone)
    # ไทย: \u0e00-\u0e7f
    # อังกฤษ: a-zA-Z0-9
    # ญี่ปุ่น (Hiragana, Katakana, Kanji): \u3040-\u30ff, \u4e00-\u9faf
    # สัญลักษณ์พื้นฐาน: \s,.()\-/:
    safe_pattern = r'[\u0e00-\u0e7fa-zA-Z0-9\u3040-\u30ff\u4e00-\u9faf\s,.()\-/:\"\'\[\]]'
    
    # 2. หาจำนวนอักขระที่ปลอดภัย
    safe_chars = len(re.findall(safe_pattern, text))
    total_chars = len(text)
    
    # 3. คำนวณ Noise Ratio (อักขระประหลาด / อักขระทั้งหมด)
    noise_ratio = 1 - (safe_chars / total_chars) if total_chars > 0 else 1

    # 4. นับสัดส่วน Punctuation ที่ "มากเกินไป" 
    # ปกติพวกอักขระเพี้ยนจะชอบเป็นเครื่องหมายแปลกๆ เช่น  , ▯, ▀, 
    special_noise = len(re.findall(r'[^\w\s\u0e00-\u0e7f\u3040-\u30ff\u4e00-\u9faf]', text))
    special_noise_ratio = special_noise / total_chars if total_chars > 0 else 1

    # --- การตัดสินใจ (Logic Gate) ---
    # ถ้า Noise Ratio สูงกว่า 2%  ตีว่า CORRUPT
    # print(f"Total Chars: {total_chars}, Safe Chars: {safe_chars}, Noise Ratio: {noise_ratio:.2%}, Special Noise Ratio: {special_noise_ratio:.2%}")
    if noise_ratio > 0.02:
        return "CORRUPT_ENCODING"
    
    return "NORMAL_TEXT"


file_path = r"D:\llm_dev\knowledge\data\Safety\standard\(A 1-0) ATTG-S-SHE 025 มาตรฐานการติดตั้ง Safety Cover Rev. 2008.pdf"

print(classify_multilingual_pdf(file_path))