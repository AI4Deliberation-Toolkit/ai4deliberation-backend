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
