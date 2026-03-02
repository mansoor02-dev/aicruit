"""
Request / Response schemas for the TTS API.
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field


class GTTSOptions(BaseModel):
    lang: str = Field("en", description="Language code, e.g. 'en', 'fr'")
    tld: str = Field("co.uk", description="Accent TLD: 'co.uk' (British), 'com' (US), 'com.au' (AU)")
    slow: bool = Field(False, description="Enable slow speech mode")


class PiperOptions(BaseModel):
    model_path: str = Field("model/en_GB-alba-medium.onnx", description="Path to the .onnx voice model")
    volume: float = Field(0.8, ge=0.0, le=2.0, description="Audio volume")
    length_scale: float = Field(0.9, ge=0.1, le=5.0, description="Speech speed — higher is slower")
    noise_scale: float = Field(0.8, ge=0.0, le=1.0, description="Audio variation")
    noise_w_scale: float = Field(1.2, ge=0.0, le=2.0, description="Speaking variation")


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000, description="Text to convert to speech")
    engine: Literal["gtts", "piper"] = Field("gtts", description="TTS engine to use")
    gtts: Optional[GTTSOptions] = Field(default_factory=GTTSOptions, description="gTTS engine options")
    piper: Optional[PiperOptions] = Field(default_factory=PiperOptions, description="PiperTTS engine options")

    model_config = {"json_schema_extra": {
        "examples": [
            {
                "text": "Welcome to the world of speech synthesis!",
                "engine": "gtts",
                "gtts": {"lang": "en", "tld": "co.uk", "slow": False}
            },
            {
                "text": "Welcome to the world of speech synthesis!",
                "engine": "piper",
                "piper": {"model_path": "model/en_GB-alba-medium.onnx", "volume": 0.8, "length_scale": 0.9}
            }
        ]
    }}


class TTSResponse(BaseModel):
    file_id: str
    download_url: str
    engine: str
    format: str