"""
PiperTTS engine — offline TTS, produces WAV.
"""

import uuid
import wave
from pathlib import Path

from piper import PiperVoice, SynthesisConfig


def synthesize(
    text: str,
    output_dir: Path,
    model_path: str = "model/en_GB-alba-medium.onnx",
    volume: float = 0.8,
    length_scale: float = 0.9,
    noise_scale: float = 0.8,
    noise_w_scale: float = 1.2,
) -> tuple[str, Path]:
    """
    Synthesize text to WAV using PiperTTS.

    Returns:
        (file_id, output_path)
    """
    model = Path(model_path)
    if not model.exists():
        raise FileNotFoundError(f"Piper model not found: {model_path}")

    file_id = str(uuid.uuid4())
    output_path = output_dir / f"{file_id}.wav"

    voice = PiperVoice.load(str(model))
    syn_config = SynthesisConfig(
        volume=volume,
        length_scale=length_scale,
        noise_scale=noise_scale,
        noise_w_scale=noise_w_scale,
        normalize_audio=False,
    )

    with wave.open(str(output_path), "wb") as wav_file:
        voice.synthesize_wav(text, wav_file, syn_config=syn_config)

    return file_id, output_path