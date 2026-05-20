"""
Upload all PDF files from a folder to a Dify knowledge base.

Usage:
    1. Edit the variables below
    2. Run: python upload_pdfs.py
"""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

# ── Configuration (edit these) ────────────────────────────────────────────────
BASE_URL = "http://192.168.212.7:8011/v1"
API_KEY = "dataset-aEZyPHFc6cdLRE7KAfsthQU2"
DATASET_ID = "59fbfc49-f973-4e3d-890a-d6803a525225"
FOLDER_PATH = r"D:\llm_dev\knowledge\ATTG STD Prep"
LOG_FILE = "upload_log.json"

TIMEOUT = httpx.Timeout(120.0, connect=10.0)

# ── data JSON payload (edit this as needed) ───────────────────────────────────
DATA_JSON = json.dumps({
  "indexing_technique": "high_quality",
  "doc_form": "text_model",
  "doc_language": "Thai",
  "process_rule": {
    "mode": "custom",
    "rules": {
      "pre_processing_rules": [
        {
          "id": "remove_extra_spaces",
          "enabled": False
        }
      ],
      "segmentation": {
        "separator": "\n\n",
        "max_tokens": 1500,
        "chunk_overlap": 300
      }
    }
  },
  "retrieval_model": {
    "search_method": "hybrid_search",
    "reranking_enable": False,
    "top_k": 5,
    "score_threshold_enabled": False,
    "reranking_mode": "weighted_score",
    "score_threshold": 0,
    "weights": {
      "weight_type": "customized",
      "vector_setting": {
        "vector_weight": 0.6,
        "embedding_model_name": "jina-v5-small-retrieval",
        "embedding_provider_name": "langgenius/ollama/ollama"
      },
      "keyword_setting": {
        "keyword_weight": 0.4
      }
    }
  },
  "embedding_model": "jina-v5-small-retrieval",
  "embedding_model_provider": "langgenius/ollama/ollama"
})


def upload_one(
    client: httpx.Client,
    base_url: str,
    dataset_id: str,
    api_key: str,
    pdf_path: Path,
) -> dict:
    url = f"{base_url}/datasets/{dataset_id}/document/create-by-file"
    headers = {"Authorization": f"Bearer {api_key}"}

    with open(pdf_path, "rb") as f:
        files = {"file": (pdf_path.name, f, "application/pdf")}
        data = {"data": DATA_JSON}
        resp = client.post(url, headers=headers, files=files, data=data)

    resp.raise_for_status()
    return resp.json()


def main() -> None:
    if not DATASET_ID:
        print("Error: DATASET_ID is not set. Edit the variable in this script.")
        sys.exit(1)
    if not API_KEY:
        print("Error: API_KEY is not set. Edit the variable in this script.")
        sys.exit(1)

    folder = Path(FOLDER_PATH)
    if not folder.is_dir():
        print(f"Error: '{folder}' is not a valid directory")
        sys.exit(1)

    pdf_files = sorted(folder.glob("*.pdf"))
    if not pdf_files:
        print(f"No PDF files found in '{folder}'")
        sys.exit(0)

    print(f"Found {len(pdf_files)} PDF(s) in '{folder}'")
    print(f"Dataset ID: {DATASET_ID}")
    print(f"Base URL:   {BASE_URL}")
    print()

    results: list[dict] = []
    success_count = 0
    fail_count = 0

    client = httpx.Client(timeout=TIMEOUT)
    try:
        for i, pdf in enumerate(pdf_files, 1):
            print(f"[{i}/{len(pdf_files)}] Uploading {pdf.name} ... ", end="", flush=True)
            start = time.time()
            entry: dict = {
                "file": pdf.name,
                "path": str(pdf),
                "status": "pending",
                "document_id": None,
                "batch": None,
                "error": None,
                "duration_s": None,
            }
            try:
                resp_data = upload_one(client, BASE_URL, DATASET_ID, API_KEY, pdf)
                duration = round(time.time() - start, 2)
                doc = resp_data.get("document", {})
                entry.update({
                    "status": "success",
                    "document_id": doc.get("id"),
                    "batch": resp_data.get("batch"),
                    "duration_s": duration,
                })
                success_count += 1
                print(f"OK ({duration}s) doc_id={doc.get('id')}")
            except httpx.HTTPStatusError as exc:
                duration = round(time.time() - start, 2)
                try:
                    err_body = exc.response.json()
                except Exception:
                    err_body = exc.response.text
                entry.update({
                    "status": "failed",
                    "error": err_body,
                    "duration_s": duration,
                })
                fail_count += 1
                print(f"FAILED ({duration}s) {err_body}")
            except Exception as exc:
                duration = round(time.time() - start, 2)
                entry.update({
                    "status": "failed",
                    "error": str(exc),
                    "duration_s": duration,
                })
                fail_count += 1
                print(f"FAILED ({duration}s) {exc}")

            results.append(entry)
    finally:
        client.close()

    # ── Write log ─────────────────────────────────────────────────────────────
    log = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dataset_id": DATASET_ID,
        "base_url": BASE_URL,
        "folder": str(folder),
        "summary": {
            "total": len(pdf_files),
            "success": success_count,
            "failed": fail_count,
        },
        "files": results,
    }

    log_path = Path(LOG_FILE)
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)

    print()
    print(f"Done. Total: {len(pdf_files)} | Success: {success_count} | Failed: {fail_count}")
    print(f"Log saved to: {log_path}")


if __name__ == "__main__":
    main()
