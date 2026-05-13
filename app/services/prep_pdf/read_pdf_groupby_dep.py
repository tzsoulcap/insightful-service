import os
import shutil
import fitz  # PyMuPDF
from pathlib import Path

def audit_knowledge_base(root_path):
    root = Path(root_path)
    # เก็บข้อมูลสถิติแยกตามแผนก
    # {dept_name: {"total": 0, "no_ocr": 0, "need_ocr": 0}}
    stats = {}

    # ตรวจสอบว่า Path มีอยู่จริงหรือไม่
    if not root.exists():
        print(f"❌ Error: Root path '{root_path}' not found.")
        return

    # ดึงรายชื่อโฟลเดอร์แผนก
    departments = [d for d in os.listdir(root) if (root / d).is_dir()]

    for dept in departments:
        stats[dept] = {"total": 0}
        dept_path = root / dept

        # ใช้ os.walk เพื่อเจาะเข้าไปใน sub-folders ทั้งหมดของแผนกนั้นๆ
        for subdir, _, files in os.walk(dept_path):
            for file in files:
                if not file.lower().endswith(".pdf"):
                    continue

                file_path = Path(subdir) / file
                stats[dept]["total"] += 1


    # --- การแสดงผลลัพธ์ (Summary Report) ---
    print("\n" + "="*22)
    print(f"{'Department':<15} | {'Total':<7}")
    print("-" * 22)
    
    for dept, data in stats.items():
        print(f"{dept:<15} | {data['total']:<7}")
    
    print("="*22)
    print("💡 Note: 'Need OCR' includes scanned images and unreadable PDFs.")


if __name__ == "__main__":    # กำหนด path ของโฟลเดอร์หลักที่เก็บข้อมูลแผนกต่างๆ
    root_folder = r"D:\llm_dev\knowledge\data"
    audit_knowledge_base(root_folder)