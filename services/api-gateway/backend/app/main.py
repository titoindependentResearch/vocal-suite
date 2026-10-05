import os
import math
import json
import asyncio
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.audio_processing import generate_lyrics_map

app = FastAPI(title="VocalSuite API Gateway")

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==============================================================================
# CARGA DE LETRAS Y UTILIDADES DE SINCRONIZACIÓN
# ==============================================================================
BASE_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LYRICS_PATH = os.path.join(BASE_BACKEND_DIR, "no_me_mires_mas_lyrics.json")
lyrics_data = []

if os.path.exists(LYRICS_PATH):
    try:
        with open(LYRICS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            lyrics_data = data.get("syllables", [])
        print(f"✅ Letras cargadas correctamente ({len(lyrics_data)} sílabas/palabras).")
    except Exception as e:
        print(f"⚠️ Error al cargar {LYRICS_PATH}: {e}")
else:
    print(f"⚠️ Archivo de letras no encontrado en {LYRICS_PATH}")


def obtener_silaba_actual(tiempo_segundos: float) -> str:
    """Busca la sílaba/palabra activa correspondiente al segundo de reproducción."""
    for item in lyrics_data:
        if item["start"] <= tiempo_segundos <= item["end"]:
            return item["text"]
    return ""

# ==============================================================================
# CONFIGURACIÓN DE DIRECTORIOS Y ARCHIVOS ESTÁTICOS
# ==============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(BASE_DIR)
SEPARATED_DIR = os.path.join(BACKEND_DIR, "separated")
PROCESSED_DIR = os.path.join(BACKEND_DIR, "processed")

os.makedirs(PROCESSED_DIR, exist_ok=True)
# Asegurar directorio processed
os.makedirs(PROCESSED_DIR, exist_ok=True)

# Copiar audio de voz por defecto si no existe en processed
default_vocal_src = "/mnt/c/tito/VocalSuite/services/api-gateway/backend/separated/htdemucs/NoMeMiresMas/vocals.wav"
default_vocal_dst = os.path.join(PROCESSED_DIR, "vocals.wav")

if not os.path.exists(default_vocal_dst) and os.path.exists(default_vocal_src):
    import shutil
    shutil.copy(default_vocal_src, default_vocal_dst)
    print("✅ Archivo vocals.wav copiado automáticamente a processed/")
app.mount("/audio-files", StaticFiles(directory=PROCESSED_DIR), name="audio-files")

PITCH_MAP_CACHE = []
current_audio_state = {
    "vocal_wav": "/mnt/c/tito/VocalSuite/services/api-gateway/backend/separated/htdemucs/NoMeMiresMas/vocals.wav",
    "pitch_map": []
}

pitch_map_json_path = os.path.join(BACKEND_DIR, "pitch_map.json")
if os.path.exists(pitch_map_json_path):
    try:
        with open(pitch_map_json_path, "r", encoding="utf-8") as f:
            PITCH_MAP_CACHE = json.load(f)
            current_audio_state["pitch_map"] = PITCH_MAP_CACHE
    except Exception as e:
        print(f"Error cargando pitch_map.json: {e}")

# ==============================================================================
# FUNCIONES DE PROCESAMIENTO DE AUDIO Y PITCH
# ==============================================================================
def hz_to_note_name(freq: float):
    if freq is None or freq <= 0:
        return "---", 0.0
    A4 = 440.0
    notes = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    semitones_from_a4 = 12 * math.log2(freq / A4)
    note_number = round(semitones_from_a4) + 69
    note_name = notes[note_number % 12]
    octave = (note_number // 12) - 1
    target_freq = A4 * (2 ** ((note_number - 69) / 12))
    return f"{note_name}{octave}", target_freq


def calculate_cents_and_status(freq: float, ref_freq: float):
    if freq <= 0 or ref_freq <= 0:
        return 0.0, "Sin señal", "#64748b"

    cents = 1200 * math.log2(freq / ref_freq)

    if abs(cents) <= 15:
        return cents, "Excelente", "#00ff88"
    elif cents > 15:
        return cents, "Sostenido", "#f59e0b"
    else:
        return cents, "Bemolizado", "#f43f5e"


def compute_pitch_from_pcm(pcm_data: bytes, sample_rate: int = 16000):
    try:
        audio_data = np.frombuffer(pcm_data, dtype=np.int16).astype(np.float32) / 32768.0
        if len(audio_data) == 0:
            return 0.0, "---", 0.0

        # 1. Calculamos la amplitud RMS real del micrófono
        rms = float(np.sqrt(np.mean(audio_data ** 2)))
        
        # Umbral equilibrado: ignora ruidos débiles pero detecta canto suave
        if rms < 0.02:
            return 0.0, "---", 0.0

        autocorr = np.correlate(audio_data, audio_data, mode='full')
        autocorr = autocorr[len(autocorr)//2:]

        # Rango vocal acotado (de 70 Hz a 500 Hz) para evitar saltos de octava
        min_lag = int(sample_rate / 500)  # Máximo 500 Hz
        max_lag = int(sample_rate / 70)   # Mínimo 70 Hz

        if len(autocorr) <= max_lag or autocorr[0] <= 0:
            return 0.0, "---", 0.0

        peak = np.argmax(autocorr[min_lag:max_lag]) + min_lag
        
        # 2. Claridad armónica moderada
        clarity = float(autocorr[peak] / autocorr[0])
        if clarity < 0.28:
            return 0.0, "---", 0.0

        freq = float(sample_rate / peak)
        note, target_freq = hz_to_note_name(freq)
        return freq, note, target_freq
    except Exception:
        return 0.0, "---", 0.0


def shift_pitch_map_data(pitch_map: list, semitones: int):
    if not pitch_map:
        return []
    factor = math.pow(2.0, semitones / 12.0)
    shifted = []
    for item in pitch_map:
        freq = item.get("freq", 0.0)
        new_freq = freq * factor if freq > 0 else 0.0
        shifted.append({
            "time": item.get("time", 0.0),
            "freq": round(new_freq, 2)
        })
    return shifted

# ==============================================================================
# ENDPOINTS REST
# ==============================================================================
@app.get("/")
async def root():
    return {"status": "online", "service": "VocalSuite API Gateway"}


@app.get("/api/pitch-map")
async def get_pitch_map():
    vocal_path = "/mnt/c/tito/VocalSuite/services/api-gateway/backend/separated/htdemucs/NoMeMiresMas/vocals.wav"
    
    # Priorizar las sílabas/letras completas cargadas desde no_me_mires_mas_lyrics.json
    lyrics = lyrics_data
    if not lyrics and os.path.exists(LYRICS_PATH):
        try:
            with open(LYRICS_PATH, "r", encoding="utf-8") as f:
                content = json.load(f)
                if isinstance(content, dict):
                    lyrics = content.get("syllables") or content.get("lyrics_map") or []
                elif isinstance(content, list):
                    lyrics = content
        except Exception as e:
            print(f"Error al releer archivo de letras: {e}")

    if not lyrics and os.path.exists(vocal_path):
        try:
            lyrics = generate_lyrics_map(vocal_path)
        except Exception:
            lyrics = []

    if isinstance(PITCH_MAP_CACHE, dict):
        pitch_data = PITCH_MAP_CACHE.get("pitch_map", [])
    else:
        pitch_data = PITCH_MAP_CACHE

    return {
        "pitch_map": pitch_data,
        "lyrics_map": lyrics
    }


@app.post("/api/audio/shift")
async def shift_pitch(semitones: int = Query(..., ge=-6, le=6)):
    vocal_wav = current_audio_state.get("vocal_wav")
    if not vocal_wav or not os.path.exists(vocal_wav):
        raise HTTPException(status_code=404, detail="Archivo vocal no encontrado")

    raw_pitch = current_audio_state["pitch_map"]
    if isinstance(raw_pitch, dict):
        raw_pitch = raw_pitch.get("pitch_map", [])

    shifted_map = shift_pitch_map_data(raw_pitch, semitones)
    shifted_filename = f"shifted_{semitones}_{os.path.basename(vocal_wav)}"
    output_shifted_path = os.path.join(PROCESSED_DIR, shifted_filename)

    factor = math.pow(2.0, semitones / 12.0)
    sample_rate = int(16000 * factor)

    cmd = f"ffmpeg -y -i '{vocal_wav}' -filter:a \"asetrate={sample_rate},atempo={1.0/factor}\" '{output_shifted_path}'"
    os.system(cmd)

    return {
        "new_audio_url": f"/audio-files/{shifted_filename}",
        "new_pitch_map": shifted_map,
        "semitones": semitones
    }

# ==============================================================================
# ENDPOINT WEBSOCKET
# ==============================================================================
@app.websocket("/api/ws/coach")
async def websocket_coach(websocket: WebSocket):
    await websocket.accept()
    print("✅ Cliente WebSocket conectado limpiamente")
    try:
        while True:
            # Recibir búfer de bytes PCM16 enviado por el navegador
            data = await websocket.receive_bytes()
            
            if not data or len(data) == 0:
                continue

            # Procesar con la función calibrada de pitch
            freq, note, target_freq = compute_pitch_from_pcm(data, sample_rate=16000)
            
            cents = 0.0
            if freq > 0 and target_freq > 0:
                cents = float(1200 * np.log2(freq / target_freq))

            # Devolver respuesta JSON al cliente web incluyendo la sílaba/palabra activa
            response = {
                "freq": float(freq),
                "note": note,
                "target": note,
                "cents": float(cents),
                "color": "#00ff88" if abs(cents) <= 15 else ("#f59e0b" if cents > 0 else "#f43f5e")
            }
            await websocket.send_json(response)

    except WebSocketDisconnect:
        print("Cliente WebSocket desconectado de forma limpia")
    except Exception as e:
        import traceback
        print("❌ ERROR CRÍTICO EN WEBSOCKET:")
        traceback.print_exc()