import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

def freq_to_note(freq: float) -> str:
    if freq <= 0:
        return "---"
    h = round(12 * np.log2(freq / 440.0) + 69)
    n = h % 12
    octave = (h // 12) - 1
    return f"{NOTE_NAMES[n]}{octave}"

def compute_pitch(audio_data: np.ndarray, sample_rate: int = 16000) -> float:
    try:
        float_data = audio_data.astype(np.float32)
        
        # Umbral RMS optimizado para no perder notas al cantar normal
        rms = np.sqrt(np.mean(float_data ** 2))
        if rms < 0.002:  
            return 0.0

        float_data = float_data - np.mean(float_data)
        
        correlation = np.correlate(float_data, float_data, mode='full')
        correlation = correlation[len(correlation)//2:]
        
        # Rango vocal estándar para voz masculina de salsa (85 Hz a 400 Hz)
        min_lag = int(sample_rate / 400)
        max_lag = int(sample_rate / 85)
        
        if max_lag >= len(correlation) or min_lag >= max_lag:
            return 0.0

        sub_corr = correlation[min_lag:max_lag]
        if len(sub_corr) == 0:
            return 0.0

        peak_threshold = 0.1 * correlation[0]
        peaks = []
        for i in range(1, len(sub_corr) - 1):
            if sub_corr[i] > sub_corr[i-1] and sub_corr[i] > sub_corr[i+1] and sub_corr[i] > peak_threshold:
                peaks.append(i + min_lag)
                
        if not peaks:
            peak = np.argmax(sub_corr) + min_lag
        else:
            max_val = max(correlation[p] for p in peaks)
            # Seleccionar el pico más grave (mayor lag) con buena correlación
            valid_peaks = [p for p in peaks if correlation[p] >= 0.6 * max_val]
            peak = max(valid_peaks) if valid_peaks else peaks[0]

        if correlation[0] > 0 and correlation[peak] < 0.04 * correlation[0]:
            return 0.0

        pitch = sample_rate / peak
        return float(pitch) if 85 <= pitch <= 400 else 0.0
    except Exception as e:
        return 0.0

@router.websocket("/ws/coach")
async def coach_websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_bytes()
            audio_np = np.frombuffer(data, dtype=np.float32)
            
            pitch = compute_pitch(audio_np)
            target = freq_to_note(pitch) if pitch > 0 else "---"
            
            await websocket.send_json({
                "freq": float(pitch),
                "target": target
            })
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket error: {e}")