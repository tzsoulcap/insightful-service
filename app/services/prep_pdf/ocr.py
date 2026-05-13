import typhoon_ocr.ocr_utils
from unittest.mock import patch
from typhoon_ocr import ocr_document
import time
from pypdf import PdfReader

# สร้างฟังก์ชันจำลองเพื่อดักแก้ค่าก่อนส่งไป vLLM
original_create = None

def patched_create(*args, **kwargs):
    if 'max_tokens' in kwargs and kwargs['max_tokens'] == 16384:
        kwargs['max_tokens'] = 8192 # บังคับให้เหลือแค่ 4096 เพื่อให้รันใน server 8k ได้, 4096, 8192, 16384
    return original_create(*args, **kwargs)

# เริ่มการ Patch
import openai.resources.chat.completions
original_create = openai.resources.chat.completions.Completions.create
openai.resources.chat.completions.Completions.create = patched_create

file_path = r"D:\llm_dev\knowledge\data\Safety\standard\ATTG-S-SHE 059 การติดตั้งอุปกรณ์ตัดไฟฟ้ารั่ว (TKAS-B-2-2) Rev.2.pdf"
reader = PdfReader(file_path)
total_pages = len(reader.pages)


start_time = time.time()
results = []
for page in range(1, total_pages + 1):
    markdown = ocr_document(pdf_or_image_path=file_path, 
                            page_num=page,
                            model = "typhoon-ai/typhoon-ocr1.5-2b" , 
                            target_image_dim=1500,
                            figure_language = "Thai" , 
                        task_type="v1.5", 
                        base_url='http://192.168.212.7:8002/v1', 
                        api_key='no-key')
    results.append(markdown)
    print(f"Page {page}/{total_pages} processed. ================================")
    print(markdown)  
full_text = "\n\n".join(results)
end_time = time.time()
duration = end_time - start_time
print(f"Total Request Time: {duration:.2f} seconds")
print("OCR Result:====================================")
print(full_text)