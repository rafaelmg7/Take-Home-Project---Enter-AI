from fastapi import FastAPI, UploadFile, File, Form, HTTPException
import json
import asyncio
import io
import logging

from app.pdf_parser import parse_pdf
from app.pipeline import run_extraction_pipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="PDF Data Extraction API",
    description="Extract structured data from PDFs",
    version="0.1.0"
)


@app.get("/")
async def root():
    return {"status": "ok", "service": "pdf-extraction-api"}


@app.post("/extract")
async def extract_data(
    label: str = Form(...),
    extraction_schema: str = Form(...),
    pdf: UploadFile = File(...)
):
    """Extract structured data from PDF document."""
    TIMEOUT_SECONDS = 9.0

    try:
        try:
            schema_dict = json.loads(extraction_schema)
        except json.JSONDecodeError as e:
            raise HTTPException(400, f"Invalid JSON extraction_schema: {str(e)}")

        if not schema_dict:
            raise HTTPException(400, "extraction_schema cannot be empty")

        if not pdf.filename:
            raise HTTPException(400, "PDF filename is required")

        if not pdf.filename.lower().endswith('.pdf'):
            raise HTTPException(400, "Only PDF files are accepted")

        pdf_content = await pdf.read()

        if not pdf_content:
            raise HTTPException(400, "PDF file is empty")

        try:
            parse_result = await asyncio.wait_for(
                asyncio.to_thread(parse_pdf, io.BytesIO(pdf_content)),
                timeout=TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            raise HTTPException(408, f"Parsing exceeded {TIMEOUT_SECONDS}s timeout")

        if not parse_result.get("lines"):
            raise HTTPException(400, "No text content found in PDF")

        extraction_result = await asyncio.to_thread(
            run_extraction_pipeline,
            pdf_lines=parse_result.get("lines", []),
            doc_text=parse_result.get("full_text", ""),
            schema=schema_dict,
            label=label,
            timeout_seconds=TIMEOUT_SECONDS
        )

        return {
            "status": "success",
            "metadata": {
                "processing_time": extraction_result.get("metadata", {}).get("processing_time", 0.0),
                "llm_used": extraction_result.get("metadata", {}).get("llm_used", False),
            },
            "fields": extraction_result.get("fields", {}),
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Extraction failed: {str(e)}")
        raise HTTPException(500, f"Internal server error: {str(e)}")
