from pathlib import Path
import parselmouth
import numpy as np
from scipy.spatial.distance import cdist
from fastdtw import fastdtw

class CoachService:
    @staticmethod
    def extract_pitch_curve(audio_path: Path, time_step: float = 0.05) -> list[dict]:
        """
        Extrae la curva tonal (F0 en Hz y nota MIDI) desde un archivo de audio usando Praat.
        Rango vocal estándar: 75 Hz (E2) a 600 Hz (D5).
        """
        sound = parselmouth.Sound(str(audio_path))
        pitch = sound.to_pitch(time_step=time_step, pitch_floor=75.0, pitch_ceiling=600.0)
        
        pitch_values = pitch.selected_array['frequency']
        timestamps = pitch.xs()
        
        results = []
        for t, freq in zip(timestamps, pitch_values):
            if freq > 0:  # Segmento sonorizado
                midi_note = round(69 + 12 * np.log2(freq / 440.0), 2)
                results.append({
                    "time": round(float(t), 3),
                    "frequency_hz": round(float(freq), 2),
                    "midi_note": midi_note
                })
        return results

    @staticmethod
    def evaluate_performance(user_audio_path: Path, ref_audio_path: Path) -> dict:
        """
        Compara la interpretación vocal del usuario con una referencia guía.
        Retorna el porcentaje de afinación, desviación promedio en cents y tesitura alcanzada.
        """
        user_curve = CoachService.extract_pitch_curve(user_audio_path)
        ref_curve = CoachService.extract_pitch_curve(ref_audio_path)

        if not user_curve or not ref_curve:
            return {
                "score_percentage": 0.0,
                "status": "error",
                "message": "No se detectó suficiente señal vocal en alguna de las grabaciones."
            }

        # Extraer secuencias MIDI para la comparación
        user_midi = np.array([p["midi_note"] for p in user_curve]).reshape(-1, 1)
        ref_midi = np.array([p["midi_note"] for p in ref_curve]).reshape(-1, 1)

        # Aplicar Dynamic Time Warping (DTW) para alinear temporalmente ambas señales
        distance, path = fastdtw(user_midi, ref_midi, dist=lambda x, y: abs(x - y))

        # Calcular desviaciones en semitonos y en cents (1 semitono = 100 cents)
        diffs_semitones = [abs(user_midi[u_idx][0] - ref_midi[r_idx][0]) for u_idx, r_idx in path]
        diffs_cents = [d * 100.0 for d in diffs_semitones]

        avg_cents_error = float(np.mean(diffs_cents))

        # Puntuación: 0 cents de error = 100%, 50 cents de error (1/2 semitono) = ~50%
        # Se penaliza exponencialmente el error
        in_tune_points = sum(1 for c in diffs_cents if c <= 50)  # Considerado afinado si está dentro de ±50 cents
        score_percentage = round((in_tune_points / len(diffs_cents)) * 100, 2)

        # Tesitura (Rango de notas MIDI alcanzado por el usuario)
        user_notes = [p["midi_note"] for p in user_curve]
        min_midi = float(np.min(user_notes))
        max_midi = float(np.max(user_notes))

        return {
            "score_percentage": score_percentage,
            "average_error_cents": round(avg_cents_error, 2),
            "total_aligned_frames": len(path),
            "user_tessitura": {
                "min_midi_note": min_midi,
                "max_midi_note": max_midi
            },
            "status": "success"
        }