# insightful-service

Middleware service ระหว่าง Frontend และ [Dify.ai](https://dify.ai) — จัดการ user permission ในระดับ dataset และ stream คำตอบกลับไปยัง client ผ่าน Server-Sent Events (SSE)

## Features

- **Chat Streaming** — รับคำถามจาก client แล้ว proxy แบบ streaming ไปยัง Dify `/chat-messages`
- **Dataset Permission** — ตรวจสอบสิทธิ์ user จาก SQLite ก่อนส่งคำถาม (หาก user ไม่มี dataset ใดเลยจะได้รับ `403`)
- **Configurable User Header** — อ่าน user identity จาก HTTP header ที่กำหนดเองได้ (ค่าเริ่มต้น `X-User-Id`)
- **CORS** — รองรับการกำหนด allowed origins ผ่าน environment variable

## Tech Stack

| Layer | Library |
|---|---|
| Web Framework | FastAPI + Uvicorn |
| Database ORM | SQLAlchemy (async) + aiosqlite |
| HTTP Client | httpx |
| Config | pydantic-settings |

## Project Structure

```
app/
├── api/
│   ├── deps.py          # FastAPI dependencies (auth, db, services)
│   └── v1/
│       └── chat.py      # POST /v1/chat endpoint
├── core/
│   ├── config.py        # Settings (pydantic-settings)
│   └── database.py      # Async SQLAlchemy engine & session
├── models/
│   └── user_permission.py   # ORM model: user_permissions table
├── repositories/
│   └── user_permission.py   # DB queries
├── schemas/
│   └── chat.py          # Request / Response schemas
├── services/
│   └── dify.py          # Dify API client (streaming)
└── main.py              # App factory, CORS, router mount
```

## Getting Started

### Prerequisites

- Python 3.11+
- Dify.ai account และ API Key

### Installation

```bash
# Clone และสร้าง virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

# ติดตั้ง dependencies
pip install -r requirements.txt
```

### Configuration

สร้างไฟล์ `.env` ที่ root ของโปรเจกต์:

```env
# Dify
DIFY_BASE_URL=https://api.dify.ai/v1
DIFY_API_KEY=your-dify-api-key

# Database (optional — ค่าเริ่มต้นใช้ SQLite)
DATABASE_URL=sqlite+aiosqlite:///./insightful.db

# Header ที่ใช้อ่าน user identity (optional)
USER_ID_HEADER=X-User-Id

# CORS (optional — ค่าเริ่มต้นอนุญาตทุก origin)
CORS_ORIGINS=["https://your-frontend.com"]
```

### Run

```bash
uvicorn app.main:app --reload
```

Service จะรันที่ `http://localhost:8000`

## API

### `GET /health`

ตรวจสอบสถานะของ service

```json
{ "status": "ok" }
```

---

### `POST /v1/chat`

ส่งคำถามไปยัง Dify และรับคำตอบแบบ streaming (SSE)

**Headers**

| Header | Required | Description |
|---|---|---|
| `X-User-Id` | Yes | User identifier (ชื่อ header กำหนดได้ผ่าน `USER_ID_HEADER`) |

**Request Body**

```json
{
  "query": "คำถามของ user",
  "conversation_id": "uuid-ของ conversation (optional)",
  "inputs": {},
  "user": "override user identifier ที่ส่งไป Dify (optional)"
}
```

**Response**

`Content-Type: text/event-stream` — SSE events จาก Dify โดยตรง

```
data: {"event": "message", "answer": "...", "conversation_id": "..."}

data: {"event": "message_end", ...}
```

## Database

ตาราง `user_permissions` เก็บสิทธิ์การเข้าถึง dataset ของแต่ละ user

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Auto-increment |
| `user_id` | VARCHAR | User identifier |
| `dataset_id` | VARCHAR | Dify dataset ID |

ตารางถูกสร้างอัตโนมัติเมื่อ service เริ่มต้น เพิ่ม record ด้วย SQL ตรง หรือผ่าน tool ที่ต้องการ

```sql
INSERT INTO user_permissions (user_id, dataset_id)
VALUES ('alice', 'dataset-uuid-here');
```
