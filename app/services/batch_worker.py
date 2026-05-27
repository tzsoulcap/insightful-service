import asyncio
import json
import logging
import os
import traceback
from datetime import datetime, timezone

import docker
import docker.errors
import httpx

from app.core.config import get_settings
from app.core.database import async_session
from app.models.batch import Batch, ProcessPdf
from app.services.batch_service import get_batch, update_batch_status, update_process_pdf
from app.services.dify import DifyService
from app.services.dify_cleanup import cleanup_dify_images
from app.services.prep_pdf.init_data_pipeline import (
    classify_pdf,
    embed_hidden_text_to_temp,
    format_ocr_page,
    ocr_all_pages,
    remove_text_layer_to_temp,
)
from app.services.prep_pdf.misspell_service import correct_misspell

logger = logging.getLogger(__name__)

_OCR_CONTAINER_NAME = "vllm-vllm-1"
_HEALTH_POLL_INTERVAL = 5   # seconds between health checks
_HEALTH_POLL_MAX = 30       # max attempts
_CONTAINER_BOOT_WAIT = 90  # seconds to wait after container.start()


def _build_health_url(ocr_base_url: str) -> str:
    # /v1/models is a reliable readiness indicator for vLLM:
    # it only returns 200 once the model is fully loaded and ready for inference.
    # /health returns 200 too early (while the model is still loading).
    return ocr_base_url.rstrip("/") + "/models"


async def _ensure_ocr_ready(settings) -> None:
    """Make sure the OCR container is running and the vLLM server is healthy."""
    health_url = _build_health_url(settings.OCR_BASE_URL)

    # ── Check container status ──────────────────────────────────────────────
    def _container_status() -> str:
        try:
            client = docker.from_env()
            container = client.containers.get(_OCR_CONTAINER_NAME)
            return container.status
        except docker.errors.NotFound:
            return "not_found"
        except docker.errors.DockerException as exc:
            logger.error("Docker error while checking OCR container: %s", exc)
            return "docker_error"

    container_status = await asyncio.to_thread(_container_status)
    logger.info("OCR container '%s' status: %s", _OCR_CONTAINER_NAME, container_status)

    if container_status not in ("running",):
        if container_status in ("not_found", "docker_error"):
            logger.warning("Cannot start OCR container (%s) — proceeding anyway", container_status)
            return

        # Start the stopped container
        def _start_container() -> None:
            client = docker.from_env()
            container = client.containers.get(_OCR_CONTAINER_NAME)
            container.start()

        logger.info("Starting OCR container '%s' ...", _OCR_CONTAINER_NAME)
        await asyncio.to_thread(_start_container)
        logger.info("Waiting %d s for container to initialize ...", _CONTAINER_BOOT_WAIT)
        await asyncio.sleep(_CONTAINER_BOOT_WAIT)

    # ── Poll health endpoint ────────────────────────────────────────────────
    logger.info("Polling OCR health: %s (max %d attempts)", health_url, _HEALTH_POLL_MAX)
    async with httpx.AsyncClient(timeout=10.0) as hclient:
        for attempt in range(1, _HEALTH_POLL_MAX + 1):
            try:
                resp = await hclient.get(health_url)
                if resp.status_code == 200:
                    logger.info("OCR service is ready (attempt %d/%d)", attempt, _HEALTH_POLL_MAX)
                    return
                logger.warning("Health check attempt %d/%d → HTTP %d", attempt, _HEALTH_POLL_MAX, resp.status_code)
            except Exception as exc:
                logger.warning("Health check attempt %d/%d failed: %s", attempt, _HEALTH_POLL_MAX, exc)
            if attempt < _HEALTH_POLL_MAX:
                await asyncio.sleep(_HEALTH_POLL_INTERVAL)

    logger.error("OCR service not healthy after %d attempts — proceeding anyway", _HEALTH_POLL_MAX)


async def _stop_ocr_container() -> None:
    """Stop the OCR vLLM container after all files are processed."""
    def _stop() -> None:
        try:
            client = docker.from_env()
            container = client.containers.get(_OCR_CONTAINER_NAME)
            if container.status == "running":
                container.stop()
                logger.info("OCR container '%s' stopped.", _OCR_CONTAINER_NAME)
            else:
                logger.info("OCR container '%s' already stopped (status: %s).", _OCR_CONTAINER_NAME, container.status)
        except docker.errors.NotFound:
            logger.warning("OCR container '%s' not found when stopping.", _OCR_CONTAINER_NAME)
        except docker.errors.DockerException as exc:
            logger.error("Failed to stop OCR container: %s", exc)

    await asyncio.to_thread(_stop)

# Default Dify upload payload (same as upload_pdfs.py)
_UPLOAD_DATA_JSON = json.dumps({
    "indexing_technique": "high_quality",
    "doc_form": "text_model",
    "doc_language": "Thai",
    "process_rule": {
        "mode": "custom",
        "rules": {
            "pre_processing_rules": [
                {"id": "remove_extra_spaces", "enabled": False}
            ],
            "segmentation": {
                "separator": "\n\n",
                "max_tokens": 1500,
                "chunk_overlap": 300,
            },
        },
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
                "embedding_provider_name": "langgenius/ollama/ollama",
            },
            "keyword_setting": {"keyword_weight": 0.4},
        },
    },
    "embedding_model": "jina-v5-small-retrieval",
    "embedding_model_provider": "langgenius/ollama/ollama",
})


async def _process_single_file(
    item: ProcessPdf,
    dataset_id: str,
    dify_service: DifyService,
    settings,
) -> None:
    """Process one PDF through the full pipeline and upload to Dify."""
    async with async_session() as session:
        # Re-attach item to this session
        item = await session.get(ProcessPdf, item.id)
        if item is None:
            return

        temp_files: list[str] = []
        try:
            # ── status → processing ──
            await update_process_pdf(session, item, status="processing")
            await session.commit()

            pdf_path = item.original_file_path

            # ── classify ──
            pdf_type = await asyncio.to_thread(classify_pdf, pdf_path)
            await update_process_pdf(session, item, pdf_type=pdf_type)
            await session.commit()

            # ── pipeline (non-NORMAL_TEXT) ──
            if pdf_type != "NORMAL_TEXT":
                # Step 1: rasterize
                await update_process_pdf(session, item, current_step="rasterizing")
                await session.commit()
                ocr_source = await asyncio.to_thread(remove_text_layer_to_temp, pdf_path)
                temp_files.append(ocr_source)

                # Step 2: OCR
                await update_process_pdf(session, item, current_step="ocr")
                await session.commit()
                raw_pages = await asyncio.to_thread(ocr_all_pages, ocr_source)

                # Step 3: format
                await update_process_pdf(session, item, current_step="formatting")
                await session.commit()
                formatted_pages = [format_ocr_page(p) for p in raw_pages]

                # Step 4: misspell correction
                await update_process_pdf(session, item, current_step="correcting")
                await session.commit()
                corrected_pages: list[str] = []
                for page_text in formatted_pages:
                    corrected = await asyncio.to_thread(
                        correct_misspell,
                        page_text,
                        settings.MISSPELL_API_KEY,
                        settings.MISSPELL_BASE_URL,
                    )
                    corrected_pages.append(corrected)

                # Step 5: embed invisible text
                await update_process_pdf(session, item, current_step="embedding")
                await session.commit()
                output_temp = await asyncio.to_thread(
                    embed_hidden_text_to_temp, ocr_source, corrected_pages
                )
                temp_files.append(output_temp)

                # Use the processed file for upload
                upload_path = output_temp
            else:
                # NORMAL_TEXT — upload original directly
                upload_path = pdf_path

            # ── status → success (pipeline done) ──
            await update_process_pdf(session, item, status="success", current_step=None)
            await session.commit()

            # ── upload to Dify ──
            await update_process_pdf(session, item, status="uploading")
            await session.commit()

            with open(upload_path, "rb") as f:
                file_content = f.read()

            resp_data = await dify_service.create_document_by_file(
                dataset_id=dataset_id,
                file_content=file_content,
                filename=item.filename,
                data_json=_UPLOAD_DATA_JSON,
            )

            doc = resp_data.get("document", {})
            await update_process_pdf(
                session,
                item,
                status="uploaded",
                dify_document_id=doc.get("id"),
                dify_batch=resp_data.get("batch"),
            )
            await session.commit()
            logger.info("  [uploaded] %s → doc_id=%s", item.filename, doc.get("id"))

        except Exception:
            tb = traceback.format_exc()
            logger.error("  [error] %s: %s", item.filename, tb)
            await update_process_pdf(
                session, item, status="error", current_step=None, error_msg=tb
            )
            await session.commit()

        finally:
            for tmp in temp_files:
                try:
                    if os.path.exists(tmp):
                        os.remove(tmp)
                except Exception:
                    pass


async def run_batch(batch_id: str) -> None:
    """Main entry point — run by the scheduler."""
    settings = get_settings()
    dify_service = DifyService(settings)

    logger.info("=" * 60)
    logger.info("Starting batch %s", batch_id)

    async with async_session() as session:
        batch = await get_batch(session, batch_id)
        if batch is None:
            logger.error("Batch %s not found", batch_id)
            return

        # ── batch → processing ──
        await update_batch_status(
            session, batch, status="processing", started_at=datetime.now(timezone.utc)
        )
        await session.commit()

        files = list(batch.files)

    # Process each file (each gets its own session)
    success_count = 0
    error_count = 0

    # ── Ensure OCR container is running and healthy ───────────────────────────
    await _ensure_ocr_ready(settings)

    for idx, item in enumerate(files, 1):
        logger.info("[%d/%d] Processing %s", idx, len(files), item.filename)
        await _process_single_file(item, batch.dataset_id, dify_service, settings)

        # Reload item status to count
        async with async_session() as session:
            refreshed = await session.get(ProcessPdf, item.id)
            if refreshed and refreshed.status == "uploaded":
                success_count += 1
            else:
                error_count += 1

    # ── Stop OCR container after last file ────────────────────────────────────
    await _stop_ocr_container()

    # ── Cleanup Dify image records + storage files ───────────────────────────
    await cleanup_dify_images(batch.dataset_id, settings)

    # ── batch → completed ──
    async with async_session() as session:
        batch = await get_batch(session, batch_id)
        if batch:
            await update_batch_status(
                session, batch, status="completed", completed_at=datetime.now(timezone.utc)
            )
            await session.commit()

    logger.info("=" * 60)
    logger.info(
        "Batch %s done. Total: %d | Uploaded: %d | Failed: %d",
        batch_id, len(files), success_count, error_count,
    )


async def run_single_file(batch_id: str, file_id: str) -> None:
    """Retry a single ProcessPdf entry — called by the scheduler on retry requests."""
    settings = get_settings()
    dify_service = DifyService(settings)

    logger.info("Retrying file %s in batch %s", file_id, batch_id)

    async with async_session() as session:
        batch = await get_batch(session, batch_id)
        if batch is None:
            logger.error("Batch %s not found for retry", batch_id)
            return
        item = await session.get(ProcessPdf, file_id)
        if item is None or item.batch_id != batch_id:
            logger.error("ProcessPdf %s not found in batch %s", file_id, batch_id)
            return
        dataset_id = batch.dataset_id

    await _ensure_ocr_ready(settings)
    await _process_single_file(item, dataset_id, dify_service, settings)
    await _stop_ocr_container()
    await cleanup_dify_images(dataset_id, settings)

    logger.info("Retry complete for file %s", file_id)
