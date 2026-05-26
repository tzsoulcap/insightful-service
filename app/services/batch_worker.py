import asyncio
import json
import logging
import os
import traceback
from datetime import datetime, timezone

from app.core.config import get_settings
from app.core.database import async_session
from app.models.batch import Batch, ProcessPdf
from app.services.batch_service import get_batch, update_batch_status, update_process_pdf
from app.services.dify import DifyService
from app.services.prep_pdf.init_data_pipeline import (
    classify_pdf,
    embed_hidden_text_to_temp,
    format_ocr_page,
    ocr_all_pages,
    remove_text_layer_to_temp,
)
from app.services.prep_pdf.misspell_service import correct_misspell

logger = logging.getLogger(__name__)

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
