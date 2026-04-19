from pathlib import Path
from unittest.mock import patch
from bridge.audio_processor import inspect_file, get_duration


@patch("bridge.audio_processor.ffmpeg.probe")
def test_inspect_file_detects_video(mock_probe, tmp_path):
    mock_probe.return_value = {
        "streams": [{"codec_type": "video"}, {"codec_type": "audio"}],
        "format": {"duration": "120.0"},
    }
    f = tmp_path / "rec.mp4"
    f.write_bytes(b"fake")
    assert inspect_file(f) == "video"


@patch("bridge.audio_processor.ffmpeg.probe")
def test_inspect_file_detects_audio(mock_probe, tmp_path):
    mock_probe.return_value = {
        "streams": [{"codec_type": "audio"}],
        "format": {"duration": "45.0"},
    }
    f = tmp_path / "rec.webm"
    f.write_bytes(b"fake")
    assert inspect_file(f) == "audio"


@patch("bridge.audio_processor.ffmpeg.probe")
def test_get_duration(mock_probe, tmp_path):
    mock_probe.return_value = {
        "streams": [],
        "format": {"duration": "3661.5"},
    }
    f = tmp_path / "audio.webm"
    f.write_bytes(b"fake")
    assert get_duration(f) == 3661.5
