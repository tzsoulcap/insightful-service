"""
Misspell Correction Service
===========================
Calls a Dify chat-messages endpoint to correct OCR misspellings in a text page.
Returns the corrected text, or the original if the call fails or returns no result.
"""

import json
import logging
import re

import httpx

log = logging.getLogger(__name__)


def correct_misspell(text: str, api_key: str, base_url: str) -> str:
    """
    Send `text` to the Dify misspell-correction app and return the corrected version.

    The Dify app is expected to reply with a JSON block of the form:
        ```json
        {"CORRECTED": "...corrected text..."}
        ```
    (optionally wrapped in a <think>...</think> block that is stripped first)

    Falls back to the original `text` on any error.
    """
    if not text.strip():
        log.debug("      [misspell] Skipping empty text.")
        return text

    log.info("      [misspell] Sending %d chars to %s …", len(text), base_url)
    url = f"{base_url.rstrip('/')}/chat-messages"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "inputs": {},
        "query": text,
        "response_mode": "blocking",
        "conversation_id": "",
        "user": "pdf-pipeline",
        "files": [],
    }

    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=360)
        response.raise_for_status()
        answer: str = response.json().get("answer", "")
        log.info("      [misspell] Response received (%d chars).", len(answer))
    except Exception as exc:
        log.warning("      [misspell] Request failed (%s) — using original text.", exc)
        return text  # fallback: return original on network / parse error

    # Strip <think>...</think> reasoning block if present
    answer = re.sub(r"<think>.*?</think>", "", answer, flags=re.DOTALL).strip()

    # Extract the JSON block from the answer
    match = re.search(r"```json\s*(\{.*?\})\s*```", answer, flags=re.DOTALL)
    if not match:
        # Fallback: try a bare JSON object without code fences
        match = re.search(r"(\{.*?\})", answer, flags=re.DOTALL)

    if match:
        try:
            result = json.loads(match.group(1))
            corrected = result.get("CORRECTED")
            if corrected:
                log.info("      [misspell] Correction applied (%d → %d chars).", len(text), len(corrected))
                return corrected
        except json.JSONDecodeError as exc:
            log.warning("      [misspell] JSON parse error (%s) — using original text.", exc)

    log.warning("      [misspell] Could not extract CORRECTED field — using original text.")
    return text  # fallback: return original if parsing fails
