import subprocess
from pathlib import Path
import numpy as np
from pedalboard import Pedalboard, PitchShift
from pedalboard.io import AudioFile

class PitchService:
    @staticmethod
    def transpose_audio(input_path: Path, output_path: Path, semitones: int) -> Path:
        wav_input = input_path.with_suffix(".temp_in.wav")
        wav_output = output_path.with_suffix(".temp_out.wav")

        try:
            # 1. Extraer audio estéreo limpio
            subprocess.run(
                [
                    "ffmpeg", "-y", "-i", str(input_path),
                    "-vn", "-ac", "2", "-acodec", "pcm_s16le", "-ar", "44100",
                    str(wav_input)
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            # 2. Cargar matriz de audio en memoria
            with AudioFile(str(wav_input)) as f:
                audio = f.read(f.frames)  # Forma: (2, num_muestras)
                samplerate = f.samplerate

            board = Pedalboard([PitchShift(semitones=semitones)])

            # 3. Decodificación Mid/Side para blindar la voz central contra cancelación de fase
            if audio.shape[0] == 2:
                left = audio[0]
                right = audio[1]

                # Mid = Centro (Voz líder e instrumentos centrales)
                # Side = Laterales (Efectos e instrumentos estéreo)
                mid = (left + right) / 2.0
                side = (left - right) / 2.0

                # Procesar Mid y Side como canales monocanal independientes
                mid_shifted = board(mid[np.newaxis, :], samplerate)[0]
                side_shifted = board(side[np.newaxis, :], samplerate)[0]

                # Reconstruir canales Estéreo L/R
                left_out = mid_shifted + side_shifted
                right_out = mid_shifted - side_shifted
                effected = np.stack([left_out, right_out])
            else:
                effected = board(audio, samplerate)

            # 4. Guardar el audio procesado
            with AudioFile(str(wav_output), 'w', samplerate, effected.shape[0]) as f:
                f.write(effected)

            # 5. Empaquetar al formato de destino
            if output_path.suffix.lower() == ".wav":
                wav_output.replace(output_path)
            else:
                subprocess.run(
                    [
                        "ffmpeg", "-y", "-i", str(wav_output),
                        "-c:a", "aac", "-b:a", "256k",
                        str(output_path)
                    ],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )

            return output_path

        finally:
            for temp in (wav_input, wav_output):
                if temp.exists():
                    temp.unlink()