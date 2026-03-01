"""Application layer – orchestrates domain + infrastructure via interfaces."""
import hashlib
import io
import logging
import wave
from typing import Optional

from domain.entities import SynthesisRequest, SynthesisResponse
from domain.interfaces import TTSService

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Simple in-process LRU cache
# ──────────────────────────────────────────────
class _TTSCache:
    def __init__(self, maxsize: int = 128):
        self._store: dict[str, SynthesisResponse] = {}
        self._order: list[str] = []
        self._maxsize = maxsize

    def _key(self, req: SynthesisRequest) -> str:
        raw = f"{req.text}|{req.voice_id}|{req.language}|{req.speaking_rate}|{req.pitch}|{req.output_format}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, req: SynthesisRequest) -> Optional[SynthesisResponse]:
        k = self._key(req)
        if k in self._store:
            logger.debug("Cache hit for key %s", k[:8])
            resp = self._store[k]
            return SynthesisResponse(
                audio_bytes=resp.audio_bytes,
                sample_rate=resp.sample_rate,
                duration=resp.duration,
                provider=resp.provider,
                cached=True,
            )
        return None

    def put(self, req: SynthesisRequest, resp: SynthesisResponse) -> None:
        k = self._key(req)
        if k in self._store:
            return
        if len(self._order) >= self._maxsize:
            oldest = self._order.pop(0)
            del self._store[oldest]
        self._store[k] = resp
        self._order.append(k)


_CACHE = _TTSCache()

# ──────────────────────────────────────────────
# Text chunking
# ──────────────────────────────────────────────
_CHUNK_SIZE = 500  # characters


def _chunk_text(text: str) -> list[str]:
    """Split on sentence boundaries, keeping chunks ≤ _CHUNK_SIZE chars."""
    import re
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    chunks, current = [], ""
    for s in sentences:
        if len(current) + len(s) + 1 <= _CHUNK_SIZE:
            current = (current + " " + s).strip()
        else:
            if current:
                chunks.append(current)
            current = s
    if current:
        chunks.append(current)
    return chunks or [text]


def _concat_wav(responses: list[SynthesisResponse]) -> SynthesisResponse:
    """Concatenate multiple WAV byte blobs into one."""
    buf = io.BytesIO()
    total_frames = 0
    sample_rate = responses[0].sample_rate
    n_channels = 1
    sampwidth = 2  # 16-bit

    # First pass: gather raw PCM
    pcm_parts = []
    for resp in responses:
        try:
            with wave.open(io.BytesIO(resp.audio_bytes)) as wf:
                sample_rate = wf.getframerate()
                n_channels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                frames = wf.readframes(wf.getnframes())
                pcm_parts.append(frames)
                total_frames += wf.getnframes()
        except Exception:
            pcm_parts.append(resp.audio_bytes)

    with wave.open(buf, "wb") as out:
        out.setnchannels(n_channels)
        out.setsampwidth(sampwidth)
        out.setframerate(sample_rate)
        for part in pcm_parts:
            out.writeframes(part)

    audio = buf.getvalue()
    duration = total_frames / sample_rate if sample_rate else sum(r.duration for r in responses)
    return SynthesisResponse(
        audio_bytes=audio,
        sample_rate=sample_rate,
        duration=duration,
        provider=responses[0].provider,
    )


# ──────────────────────────────────────────────
# Use Case
# ──────────────────────────────────────────────
class SynthesizeSpeechUseCase:
    def __init__(self, service: TTSService, fallback: Optional[TTSService] = None):
        self._service = service
        self._fallback = fallback

    def execute(self, request: SynthesisRequest) -> SynthesisResponse:
        # 1. Cache check
        cached = _CACHE.get(request)
        if cached:
            return cached

        # 2. Validate
        # (dataclass __post_init__ already validates; this is belt-and-suspenders)
        if len(request.text) > 50_000:
            raise ValueError("text exceeds maximum length of 50 000 characters")

        # 3. Chunk long text
        chunks = _chunk_text(request.text)
        logger.info("Synthesizing %d chunk(s) via %s", len(chunks), self._service.provider_name)

        responses = []
        for i, chunk in enumerate(chunks):
            chunk_req = SynthesisRequest(
                text=chunk,
                voice_id=request.voice_id,
                language=request.language,
                speaking_rate=request.speaking_rate,
                pitch=request.pitch,
                output_format=request.output_format,
            )
            responses.append(self._synthesize_with_fallback(chunk_req))

        # 4. Merge
        result = _concat_wav(responses) if len(responses) > 1 else responses[0]

        # 5. Cache & return
        _CACHE.put(request, result)
        return result

    def _synthesize_with_fallback(self, req: SynthesisRequest) -> SynthesisResponse:
        try:
            return self._service.synthesize(req)
        except Exception as primary_err:
            logger.warning("Primary provider failed: %s", primary_err)
            if self._fallback:
                logger.info("Falling back to %s", self._fallback.provider_name)
                return self._fallback.synthesize(req)
            raise