CREATE TABLE batch (
    id              TEXT PRIMARY KEY,                        -- SQLite แนะนำให้เก็บ UUID เป็น TEXT
    dataset_id      TEXT NOT NULL,                           -- Target Dataset ID ใน Dify
    dataset_name    TEXT NOT NULL,                           -- ชื่อคลังข้อมูล/แผนก เช่น "Safety"
    status          TEXT NOT NULL DEFAULT 'pending',         -- pending | processing | completed | failed
    total_files     INTEGER NOT NULL DEFAULT 0,              -- จำนวนไฟล์ทั้งหมดใน Batch (ใช้ INTEGER อิงตาม SQLite)
    created_by      TEXT,                                    -- ID หรือชื่อของผู้ที่สั่งรัน
    
    -- ส่วนควบคุมเวลา (เก็บเป็น TEXT รูปแบบ ISO8601 เช่น '2026-05-25 15:00:00')
    scheduled_at    DATETIME NULL,                               
    started_at      DATETIME NULL,                               
    completed_at    DATETIME NULL,                               
    
    -- ใช้ CURRENT_TIMESTAMP ของ SQLite จะได้เวลาสากล (UTC) เป็น TEXT อัตโนมัติ
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE process_pdf (
    id                  TEXT PRIMARY KEY,
    batch_id            TEXT NOT NULL,
    filename            TEXT NOT NULL,                       -- ชื่อไฟล์ดั้งเดิมรวมนามสกุล
    original_file_path  TEXT NOT NULL,                       -- พิกัดไฟล์ต้นฉบับ เช่น /{dataset_id}/{id}.pdf
    
    -- สถานะและประเภทใน Pipeline
    pdf_type            TEXT NULL,                           -- NORMAL_TEXT | SCANNED_PDF | CORRUPT_ENCODING
    status              TEXT NOT NULL DEFAULT 'pending',     
    current_step        TEXT NULL,                           -- rasterizing | ocr | formatting | correcting | embedding
    retry_count         INTEGER NOT NULL DEFAULT 0,          
    error_msg           TEXT NULL,                           -- เก็บ Stack trace เมื่อเกิด Error
    
    -- ข้อมูลผูกกับ Dify
    dify_document_id    TEXT NULL,                           
    dify_batch          TEXT NULL,                           
    
    created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- กำหนด Foreign Key และ Cascade Delete ตามมาตรฐาน SQLite
    FOREIGN KEY (batch_id) REFERENCES batch (id) ON DELETE CASCADE
);

CREATE INDEX idx_batch_status ON batch (status);
CREATE INDEX idx_process_pdf_batch_id ON process_pdf (batch_id);
CREATE INDEX idx_process_pdf_status ON process_pdf (status);