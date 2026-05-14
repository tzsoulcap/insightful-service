# Changelog

All notable changes to this project will be documented in this file.

Format: `[version] — YYYY-MM-DD`
Types: `Added` · `Changed` · `Fixed` · `Removed`

---

## [0.1.0] — 2026-05-14

### Added
- PDF Init Data Pipeline (`init_data_pipeline.py`) — batch process ไฟล์ PDF ทั้งโฟลเดอร์
  - classify PDF เป็น 3 ประเภท: `NORMAL_TEXT`, `CORRUPT_ENCODING`, `SCANNED_PDF`
  - OCR ด้วย Typhoon OCR (task_type `v1.5`) พร้อม fallback ผ่าน PyMuPDF เมื่อ Poppler ใช้งานไม่ได้
  - embed invisible text layer (render mode 3) รองรับ 3 ภาษา: ไทย · อังกฤษ · ญี่ปุ่น
  - segment-based font switching: Sarabun (Thai/Latin) + NotoSansJP (CJK)
  - safe copy พร้อม collision handling (`_copy`, `_copy2`, …)
  - `log.json` อัปเดตหลังทุกไฟล์ ติดตาม progress และ error แต่ละไฟล์
- API `POST /v1/pdf-pipeline/process` — process PDF ทีละไฟล์ผ่าน HTTP
- API `GET /v1/version` — ตรวจสอบ version ของ service
