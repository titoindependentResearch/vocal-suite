from pathlib import Path
from audio_separator.separator import Separator

class AudioSeparatorService:
    def __init__(self, output_dir: Path, model_name: str = "UVR_MDXNET_KARA_2.onnx"):
        self.output_dir = output_dir
        self.model_name = model_name
        self.output_dir.mkdir(exist_ok=True)

    def separate_wav(self, input_wav_path: Path) -> list[Path]:
        """Ejecuta la separación sobre el WAV normalizado y devuelve los objetos Path de salida."""
        separator = Separator(output_dir=str(self.output_dir), output_format="WAV")
        separator.load_model(model_filename=self.model_name)
        
        output_filenames = separator.separate(str(input_wav_path))
        return [self.output_dir / fname for fname in output_filenames]
