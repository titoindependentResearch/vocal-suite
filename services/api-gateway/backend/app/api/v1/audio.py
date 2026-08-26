import os
import re
import shutil
import subprocess
from enum import Enum
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse

# Importamos la clase recién creada
from app.services.separator_service import AudioSeparatorService

router = APIRouter()

UPLOAD_DIR = Path("temp_uploads")
OUTPUT_DIR = Path("temp_outputs")
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# Instancia global del servicio
separator_service = AudioSeparatorService(output_dir=OUTPUT_DIR)

ALLOWED_INPUT_EXTENSIONS = {
    ".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus",
    ".mp4", ".mov", ".webm", ".mkv", ".mpeg"
}

class OutputFormat(str, Enum):
    mp3 = "mp3"
    wav = "wav"
    flac = "flac"
    m4a = "m4a"
    aac = "aac"
    ogg = "ogg"
    opus = "opus"

def sanitize_filename(filename: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_\.-]", "_", filename)

def cleanup_files(*file_paths: Path):
    """Elimina los archivos temporales generados tras responder la petición."""
    for path in file_paths:
        if path and path.exists():
            try:
                os.remove(path)
            except Exception:
                pass

@router.post("/separate")
async def separate_audio(
    background_tasks: BackgroundTasks, 
    file: UploadFile = File(...),
    output_format: OutputFormat = Form(OutputFormat.mp3)
):
    # 1. Validar extensión de entrada
    input_ext = Path(file.filename).suffix.lower()
    if input_ext not in ALLOWED_INPUT_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Formato de entrada '{input_ext}' no soportado. Extensiones permitidas: {', '.join(sorted(ALLOWED_INPUT_EXTENSIONS))}"
        )

    clean_name = sanitize_filename(file.filename)
    raw_input_path = UPLOAD_DIR / clean_name

    with open(raw_input_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 2. Normalizar entrada a WAV 44.1kHz estéreo
    wav_path = UPLOAD_DIR / f"{raw_input_path.stem}_clean.wav"
    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-i", str(raw_input_path),
        "-ar", "44100",
        "-ac", "2",
        str(wav_path)
    ]

    try:
        subprocess.run(
            ffmpeg_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
    except subprocess.CalledProcessError as e:
        error_log = e.stderr.decode("utf-8", errors="ignore")
        cleanup_files(raw_input_path, wav_path)
        raise HTTPException(status_code=500, detail=f"Error FFmpeg al normalizar: {error_log}")

    # 3. Separación mediante el servicio desacoplado
    try:
        output_paths = separator_service.separate_wav(wav_path)

        instrumental_wav = None
        vocal_wav = None

        for file_path in output_paths:
            if "Instrumental" in file_path.name or "Instruments" in file_path.name:
                instrumental_wav = file_path
            else:
                vocal_wav = file_path

        if not instrumental_wav or not instrumental_wav.exists():
            instrumental_wav = output_paths[0]

        # 4. Convertir la salida al formato seleccionado por el usuario
        target_ext = output_format.value
        converted_output = OUTPUT_DIR / f"{Path(file.filename).stem}_instrumental_con_coros.{target_ext}"

        codec_args = []
        if target_ext == "mp3":
            codec_args = ["-c:a", "libmp3lame", "-b:a", "320k"]
        elif target_ext == "flac":
            codec_args = ["-c:a", "flac"]
        elif target_ext in ["m4a", "aac"]:
            codec_args = ["-c:a", "aac", "-b:a", "256k"]
        elif target_ext == "opus":
            codec_args = ["-c:a", "libopus", "-b:a", "190k"]
        elif target_ext == "ogg":
            codec_args = ["-c:a", "libvorbis", "-q:a", "6"]
        elif target_ext == "wav":
            codec_args = ["-c:a", "pcm_s16le"]

        convert_cmd = [
            "ffmpeg", "-y",
            "-i", str(instrumental_wav),
            *codec_args,
            str(converted_output)
        ]

        subprocess.run(
            convert_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        media_types = {
            "mp3": "audio/mpeg",
            "wav": "audio/wav",
            "flac": "audio/flac",
            "m4a": "audio/mp4",
            "aac": "audio/aac",
            "ogg": "audio/ogg",
            "opus": "audio/opus",
        }

        background_tasks.add_task(
            cleanup_files, raw_input_path, wav_path, instrumental_wav, vocal_wav, converted_output
        )

        return FileResponse(
            path=converted_output,
            filename=converted_output.name,
            media_type=media_types.get(target_ext, "application/octet-stream"),
        )

    except subprocess.CalledProcessError as e:
        error_log = e.stderr.decode("utf-8", errors="ignore")
        cleanup_files(raw_input_path, wav_path)
        raise HTTPException(status_code=500, detail=f"Error FFmpeg al exportar: {error_log}")
    except Exception as e:
        cleanup_files(raw_input_path, wav_path)
        raise HTTPException(status_code=500, detail=f"Error en Separador: {str(e)}")