"""
Interface – CLI

Usage:
  python main.py --text "Hello world" --provider local
  python main.py --text "Hello world" --provider api --output out.wav
  python main.py --file input.txt --provider auto --format mp3
"""
import argparse
import logging
import sys
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tts",
        description="Text-to-Speech CLI – clean architecture TTS system",
    )
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--text", "-t", help="Text to synthesize")
    group.add_argument("--file", "-f", type=Path, help="Path to text file")

    p.add_argument("--provider", "-p", default="auto",
                   choices=["api", "local", "auto"],
                   help="TTS backend (default: auto)")
    p.add_argument("--output", "-o", type=Path, default=Path("output.wav"),
                   help="Output file path (default: output.wav)")
    p.add_argument("--voice", default="default", help="Voice ID")
    p.add_argument("--language", "-l", default="en", help="Language code (default: en)")
    p.add_argument("--rate", type=float, default=1.0, help="Speaking rate 0.5-2.0 (default: 1.0)")
    p.add_argument("--pitch", type=float, default=0.0, help="Pitch -10 to 10 (default: 0.0)")
    p.add_argument("--format", default="wav", choices=["wav", "mp3"],
                   help="Output format (default: wav)")
    p.add_argument("--fallback", action="store_true",
                   help="Enable automatic fallback to other provider on error")
    p.add_argument("--verbose", "-v", action="store_true")
    return p


def run_cli(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s – %(message)s",
        datefmt="%H:%M:%S",
    )

    # Lazy imports keep startup fast
    from domain.entities import SynthesisRequest
    from application.use_cases import SynthesizeSpeechUseCase
    from infrastructure.factory import TTSFactory

    # Read text
    if args.text:
        text = args.text
    else:
        text = args.file.read_text(encoding="utf-8")

    # Build request
    request = SynthesisRequest(
        text=text,
        voice_id=args.voice,
        language=args.language,
        speaking_rate=args.rate,
        pitch=args.pitch,
        output_format=args.format,
    )

    # Create provider(s)
    if args.fallback:
        # api → local or local → api depending on choice
        other = "local" if args.provider == "api" else "api"
        primary_svc, fallback_svc = TTSFactory.create_with_fallback(args.provider, other)
    else:
        primary_svc = TTSFactory.create(args.provider)
        fallback_svc = None

    use_case = SynthesizeSpeechUseCase(primary_svc, fallback=fallback_svc)

    # Execute
    import time
    t0 = time.perf_counter()
    response = use_case.execute(request)
    elapsed = time.perf_counter() - t0

    # Write output
    output_path: Path = args.output
    if args.format == "mp3" and not output_path.suffix == ".mp3":
        output_path = output_path.with_suffix(".mp3")

    output_path.write_bytes(response.audio_bytes)

    print(
        f"✓ Saved {output_path}  "
        f"[provider={response.provider}, "
        f"duration={response.duration:.2f}s, "
        f"latency={elapsed:.3f}s, "
        f"cached={response.cached}]"
    )