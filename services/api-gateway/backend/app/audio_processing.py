import whisper

# Carga el modelo liviano 'base' de Whisper al iniciar la aplicación
try:
    print("Cargando modelo Whisper para transcripción de letras...")
    whisper_model = whisper.load_model("base")
except Exception as e:
    print(f"Advertencia al cargar modelo Whisper: {e}")
    whisper_model = None


def generate_lyrics_map(vocal_audio_path: str) -> list[dict]:
    """
    Transcribe la pista vocal aislada (.wav) y genera una lista de 
    intervalos de tiempo con el texto correspondiente.
    """
    if not whisper_model:
        print("Modelo Whisper no disponible.")
        return []

    try:
        # Transcribe forzando el idioma a español ("es")
        result = whisper_model.transcribe(vocal_audio_path, language="es")
        
        lyrics_map = []
        for segment in result.get("segments", []):
            lyrics_map.append({
                "start": round(segment["start"], 1),
                "end": round(segment["end"], 1),
                "text": segment["text"].strip()
            })
            
        return lyrics_map
    except Exception as e:
        print(f"Error procesando lírica con Whisper: {e}")
        return []
