import os
import json
import whisper

# Archivo de caché para guardar las frases transcritas
CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lyrics_cache.json")

def generate_lyrics_map(audio_path: str):
    # 1. Si ya se procesó previamente, retornar directo desde el archivo caché (< 1 ms)
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error leyendo caché de lírica: {e}")

    # 2. Si no existe la caché, ejecutar Whisper (solo ocurrirá la primera vez)
    if not os.path.exists(audio_path):
        return []

    try:
        print("🎙️ Transcribiendo audio con Whisper (se guardará en caché)...")
        model = whisper.load_model("base")
        result = model.transcribe(audio_path, language="es")
        
        lyrics_map = []
        for segment in result.get("segments", []):
            lyrics_map.append({
                "start": round(segment.get("start", 0.0), 2),
                "end": round(segment.get("end", 0.0), 2),
                "text": segment.get("text", "").strip()
            })

        # Guardar en archivo para las siguientes llamadas
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(lyrics_map, f, ensure_ascii=False, indent=2)

        print(f"✅ Transcripción completada y guardada en caché: {len(lyrics_map)} frases")
        return lyrics_map
    except Exception as e:
        print(f"Error procesando lírica con Whisper: {e}")
        return []