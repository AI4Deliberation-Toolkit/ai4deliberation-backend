from pathlib import Path
from typing import Literal
import ffmpeg


def inspect_file(path: Path) -> Literal["video", "audio"]:
    probe = ffmpeg.probe(str(path))
    stream_types = {s["codec_type"] for s in probe["streams"]}
    return "video" if "video" in stream_types else "audio"


def get_duration(path: Path) -> float:
    probe = ffmpeg.probe(str(path))
    return float(probe["format"]["duration"])


def extract_audio(source_path: Path, output_path: Path) -> None:
    (
        ffmpeg
        .input(str(source_path))
        .output(str(output_path), vn=None, acodec="libopus", f="webm")
        .run(quiet=True, overwrite_output=True)
    )
    source_path.unlink()


def split_into_chunks(audio_path: Path, output_dir: Path, chunk_duration: int = 30) -> list[Path]:
    pattern = str(output_dir / "chunk_%03d.webm")
    (
        ffmpeg
        .input(str(audio_path))
        .output(pattern, f="segment", segment_time=chunk_duration, reset_timestamps=1, acodec="copy")
        .run(quiet=True, overwrite_output=True)
    )
    return sorted(output_dir.glob("chunk_*.webm"))
