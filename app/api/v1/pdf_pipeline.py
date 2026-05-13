import os
import tempfile

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.services.prep_pdf.init_data_pipeline import (
    classify_pdf,
    embed_hidden_text_to_temp,
    format_ocr_page,
    ocr_all_pages,
    remove_text_layer_to_temp,
    safe_copy,
)

router = APIRouter(prefix="/pdf-pipeline", tags=["PDF Pipeline"])


@router.post(
    "/process",
    summary="Process a single PDF file",
    description=(
        "Classify the uploaded PDF, run OCR if needed, embed an invisible text layer, "
        "and save the result to `target_path`. "
        "Returns the classification and output file path."
    ),
)
async def process_pdf(
    file: UploadFile = File(..., description="PDF file to process"),
    target_path: str = Form(..., description="Absolute directory path where the output PDF will be saved"),
) -> dict:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Uploaded file must be a PDF.",
        )

    if not os.path.isabs(target_path):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="target_path must be an absolute directory path.",
        )

    # Save upload to a temp file so pipeline functions can read it from disk
    tmp_upload = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    temp_files: list[str] = [tmp_upload.name]

    try:
        content = await file.read()
        tmp_upload.write(content)
        tmp_upload.close()

        pdf_type = classify_pdf(tmp_upload.name)

        if pdf_type == "NORMAL_TEXT":
            output_path = safe_copy(tmp_upload.name, target_path, filename=file.filename)
        else:
            if pdf_type == "CORRUPT_ENCODING":
                ocr_source = remove_text_layer_to_temp(tmp_upload.name)
                temp_files.append(ocr_source)
            else:
                # SCANNED_PDF
                ocr_source = tmp_upload.name

            raw_pages       = ocr_all_pages(ocr_source)
            formatted_pages = [format_ocr_page(p) for p in raw_pages]
            output_temp     = embed_hidden_text_to_temp(ocr_source, formatted_pages)
            temp_files.append(output_temp)

            output_path = safe_copy(output_temp, target_path, filename=file.filename)

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )
    finally:
        for tmp in temp_files:
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:
                pass

    return {
        "filename": file.filename,
        "type": pdf_type,
        "output": output_path,
        "ocr_result": formatted_pages,
    }
