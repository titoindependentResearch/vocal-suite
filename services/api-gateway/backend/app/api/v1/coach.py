from pathlib import Path
import shutil
from fastapi import APIRouter, UploadFile, File, HTTPException

# Importación ajustada al módulo relativo del paquete
from app.services.coach_service import CoachService

router = APIRouter(prefix="/coach", tags=["Vocal Suite Coach"])

UPLOAD_DIR = Path("temp_uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

@router.post("/pitch-curve")
async def extract_pitch_curve_endpoint(file: UploadFile = File(...)):
    """
    Extrae la secuencia temporal de tono (F0 en Hz y nota MIDI) de un archivo de voz.
    """
    temp_input = UPLOAD_DIR / file.filename
    try:
        with open(temp_input, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        pitch_data = CoachService.extract_pitch_curve(temp_input)
        return {
            "status": "success",
            "filename": file.filename,
            "total_points": len(pitch_data),
            "pitch_curve": pitch_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error extrayendo curva de pitch: {str(e)}")
    finally:
        if temp_input.exists():
            temp_input.unlink()

@router.post("/evaluate")
async def evaluate_performance_endpoint(
    user_audio: UploadFile = File(..., description="Grabación de la voz del usuario"),
    reference_audio: UploadFile = File(..., description="Grabación de referencia (guía vocal)")
):
    """
    Evalúa la afinación de la voz del usuario comparándola contra una voz de referencia.
    Calcula el porcentaje de afinación, error promedio en cents y rango vocal alcanzado.
    """
    temp_user = UPLOAD_DIR / f"user_{user_audio.filename}"
    temp_ref = UPLOAD_DIR / f"ref_{reference_audio.filename}"

    try:
        with open(temp_user, "wb") as buffer:
            shutil.copyfileobj(user_audio.file, buffer)

        with open(temp_ref, "wb") as buffer:
            shutil.copyfileobj(reference_audio.file, buffer)

        metrics = CoachService.evaluate_performance(temp_user, temp_ref)
        return metrics

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al evaluar afinación: {str(e)}")
    finally:
        for temp_file in (temp_user, temp_ref):
            if temp_file.exists():
                temp_file.unlink()