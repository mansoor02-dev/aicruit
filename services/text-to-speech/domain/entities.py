"""Domain entities - pure Python, zero external dependencies."""
from dataclasses import dataclass

@dataclass
class SynthesisRequest:
    text: str
    voice_id: str = "default"
    language: str = "en"
    speaking_rate: float = 1.0   # 0.5 – 2.0
    pitch: float = 0.0           # -10.0 – +10.0 semitones
    output_format: str = "wav"   # "wav" | "mp3"

    def __post_init__(self):
        if not self.text or not self.text.strip():
            raise ValueError("text must not be empty")
        if not (0.5 <= self.speaking_rate <= 4.0):
            raise ValueError("speaking_rate must be between 0.5 and 4.0")
        if not (-10.0 <= self.pitch <= 10.0):
            raise ValueError("pitch must be between -10.0 and 10.0")
        if self.output_format not in ("wav", "mp3"):
            raise ValueError("output_format must be 'wav' or 'mp3'")


@dataclass
class SynthesisResponse:
    audio_bytes: bytes
    sample_rate: int
    duration: float          # seconds
    provider: str = "unknown"
    cached: bool = False