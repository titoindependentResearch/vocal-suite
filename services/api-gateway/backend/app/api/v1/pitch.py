import shutil
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from app.services.pitch_service import PitchService

router = APIRouter()

UPLOAD_DIR = Path("temp_uploads")
OUTPUT_DIR = Path("temp_outputs")
UPLOAD_DIR.mkdir(exist_ok   =True)
OUTPUT_DIR.mkdir(exist_ok=True)

@router.post("/transpose")
async def transpose_audio_endpoint(
    file: UploadFile = File(...),
    semitones: int = Form(..., ge=-12, le=12)
):
    input_file = UPLOAD_DIR / file.filename
    output_file = OUTPUT_DIR / f"pitch_{semitones}st_{file.filename}"

    try:
        with input_file.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        PitchService.transpose_audio(input_file, output_file, semitones)

        return FileResponse(
            path=output_file,
            filename=output_file.name,
            media_type="audio/wav"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en procesamiento de audio: {str(e)}")