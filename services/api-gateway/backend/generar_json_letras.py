import json
import re
import whisper

def cargar_letra_referencia(ruta_texto):
    """Carga la letra oficial, elimina etiquetas de coros/intros y extrae palabras limpias."""
    with open(ruta_texto, "r", encoding="utf-8") as f:
        contenido = f.read()
    
    # Elimina etiquetas como "CORO", "Coro", "INTRO", etc.
    contenido_limpio = re.sub(r'\b(CORO|Coro|Intro|INTRO)\b', '', contenido)
    
    # Extrae solo las palabras reales de la letra del cantante líder
    palabras = re.findall(r'\b\w+\b', contenido_limpio)
    return palabras

def generar_marcas_tiempo(audio_path, texto_path, output_json_path):
    print("🎙️ Cargando modelo Whisper para alineación detallada...")
    model = whisper.load_model("base")
    
    # 1. Cargar las palabras de la letra oficial (solo voz líder)
    palabras_referencia = cargar_letra_referencia(texto_path)
    print(f"📄 Letra cargada con {len(palabras_referencia)} palabras de la voz líder.")
    
    print(f"🎵 Procesando el archivo de audio: {audio_path}...")
    result = model.transcribe(audio_path, word_timestamps=True, language="es")
    
    # 2. Extraer todas las marcas de tiempo detectadas por Whisper
    words_detected = []
    for segment in result.get("segments", []):
        for word_info in segment.get("words", []):
            words_detected.append(word_info)

    syllables_list = []
    idx_ref = 0
    total_ref = len(palabras_referencia)

    # 3. Vincular cada marca de tiempo con la palabra real de la letra oficial
    for w in words_detected:
        if idx_ref < total_ref:
            palabra_real = palabras_referencia[idx_ref]
            syllables_list.append({
                "start": round(w.get("start", 0.0), 2),
                "end": round(w.get("end", 0.0), 2),
                "text": palabra_real,  # Palabra limpia de la voz líder
                "note": "Auto",
                "freq": 0.0
            })
            idx_ref += 1

    output_data = {
        "song": "No Me Mires Más",
        "artist": "Carlos El Grande",
        "duration": result.get("duration", 246.0),
        "syllables": syllables_list
    }

    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=4)
        
    print(f"✅ ¡Archivo JSON generado con éxito en: {output_json_path}!")

if __name__ == "__main__":
    audio_file = "/mnt/c/tito/VocalSuite/apps/web-client/static/NoMeMiresMas.wav"
    texto_file = "letra_no_me_mires_mas.txt"
    json_output = "no_me_mires_mas_lyrics.json"
    
    generar_marcas_tiempo(audio_file, texto_file, json_output)