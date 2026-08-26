import inspect
import librosa
import os
import requests

# Parche de compatibilidad para audio-separator con librosa >= 0.10
if hasattr(librosa, "get_duration"):
    _original_get_duration = librosa.get_duration

    def _patched_get_duration(*args, **kwargs):
        if "filename" in kwargs:
            kwargs["path"] = kwargs.pop("filename")
        return _original_get_duration(*args, **kwargs)

    librosa.get_duration = _patched_get_duration

from pathlib import Path

# Importaciones de la API
from app.api.v1 import audio, pdf, webhooks, pitch
from app.api.v1.coach import router as coach_router
# Importaciones para la Base de Datos SQLite
from app.db.session import Base, engine
from app.models import user  # Registra las tablas en SQLAlchemy
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Configuración de URLs para servicios internos
VOX_KERNEL_URL = os.getenv("VOX_KERNEL_URL", "http://localhost:8001")
COACH_AGENT_URL = os.getenv("COACH_AGENT_URL", "http://localhost:8002")

# Crear las tablas en vocaloff.db si aún no existen
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Vocal Suite API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers de la aplicación
app.include_router(
    audio.router, prefix="/api/v1/audio", tags=["Audio processing"]
)
app.include_router(
    pdf.router, prefix="/api/v1/pdf", tags=["PDF Generation"]
)
app.include_router(
    webhooks.router, prefix="/api/v1/webhooks", tags=["Webhooks"]
)
app.include_router(pitch.router, prefix="/api/v1/pitch", tags=["Vocal Suite - Pitch"])
app.include_router(coach_router, prefix="/api/v1")

# Servir Frontend
FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"


@app.get("/")
def read_root():
    return {"message": "VocalSuite API activa en modo Dev"}
def serve_frontend():
    return FileResponse(FRONTEND_DIR / "index.html")