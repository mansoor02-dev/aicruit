"""
gTTS engine — online TTS, produces MP3.
"""

import uuid
from pathlib import Path
from gtts import gTTS


def synthesize(
    text: str,
    output_dir: Path,
    lang: str = "en",
    tld: str = "co.uk",
    slow: bool = False,
) -> tuple[str, Path]:
    """
    Synthesize text to MP3 using gTTS.

    Returns:
        (file_id, output_path)
    """
    file_id = str(uuid.uuid4())
    output_path = output_dir / f"{file_id}.mp3"

    tts = gTTS(text=text, lang=lang, tld=tld, slow=slow)
    tts.save(str(output_path))

    return file_id, output_path