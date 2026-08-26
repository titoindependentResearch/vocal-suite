from pathlib import Path
import shutil
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from app.services.gotenberg import convert_html_to_pdf

router = APIRouter(prefix="/pdf", tags=["PDF Generation"])

UPLOAD_DIR = Path("temp_uploads")
OUTPUT_DIR = Path("temp_outputs")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

@router.post("/generate-report")
async def generate_pdf_report(file: UploadFile = File(...)):
    """
    Recibe un archivo HTML con el informe de evaluación vocal
    y lo convierte a un documento PDF descargable.
    """
    if not file.filename.endswith(".html"):
        raise HTTPException(
            status_code=400,
            detail="El archivo proporcionado debe tener formato .html"
        )

    temp_html = UPLOAD_DIR / file.filename
    output_pdf = OUTPUT_DIR / f"{temp_html.stem}.pdf"

    try:
        with open(temp_html, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        pdf_bytes = await convert_html_to_pdf(temp_html)
        
        with open(output_pdf, "wb") as f:
            f.write(pdf_bytes)

        return FileResponse(
            path=output_pdf,
            filename=output_pdf.name,
            media_type="application/pdf"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error al generar el reporte PDF: {str(e)}"
        )
    finally:
        if temp_html.exists():
            temp_html.unlink()