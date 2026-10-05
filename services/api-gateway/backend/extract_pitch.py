import json
import numpy as np
import librosa
import os

def generate_pitch_map(audio_path: str, output_json_path: str):
    print(f"🎵 Cargando audio desde: {audio_path}...")
    y, sr = librosa.load(audio_path, sr=22050)
    
    print("🔍 Ejecutando algoritmo PYIN para extracción de pitch vocal...")
    f0, voiced_flag, voiced_probs = librosa.pyin(
        y, 
        fmin=librosa.note_to_hz('E2'), 
        fmax=librosa.note_to_hz('C6')
    )
    
    times = librosa.frames_to_time(np.arange(len(f0)), sr=sr)
    
    pitch_map = []
    for t, freq in zip(times, f0):
        val = float(freq) if not np.isnan(freq) else 0.0
        pitch_map.append({
            "time": round(float(t), 3),
            "freq": round(val, 2)
        })
        
    data = {"pitch_map": pitch_map}
    
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        
    print(f"✅ ¡Mapa de frecuencias generado con éxito! Guardado en: {output_json_path} ({len(pitch_map)} puntos de referencia).")

if __name__ == "__main__":
    print("🚀 Iniciando proceso de extracción de pitch...")
    
    # Rutas alternativas de búsqueda para asegurar la localización de NoMeMiresMas.wav
    possible_paths = [
        "../../../apps/web-client/static/NoMeMiresMas.wav",
        "../../apps/web-client/static/NoMeMiresMas.wav",
        "static/NoMeMiresMas.wav",
        "NoMeMiresMas.wav"
    ]
    
    audio_file = None
    for path in possible_paths:
        if os.path.exists(path):
            audio_file = path
            break
            
    output_json = "pitch_map.json"
    
    if audio_file:
        generate_pitch_map(audio_file, output_json)
    else:
        print("❌ Error: No se encontró 'NoMeMiresMas.wav'. Verifica la presencia del archivo en 'apps/web-client/static/'.")