from pathlib import Path
from unittest.mock import patch, MagicMock
from bridge.audio_processor import inspect_file, get_duration, extract_audio, split_into_chunks


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


@patch("bridge.audio_processor.ffmpeg")
def test_extract_audio_runs_ffmpeg_and_deletes_source(mock_ffmpeg, tmp_path):
    source = tmp_path / "rec.mp4"
    source.write_bytes(b"fake video")
    output = tmp_path / "audio.webm"

    mock_stream = MagicMock()
    mock_ffmpeg.input.return_value.output.return_value = mock_stream

    extract_audio(source, output)

    mock_ffmpeg.input.assert_called_once_with(str(source))
    mock_ffmpeg.input.return_value.output.assert_called_once_with(
        str(output), vn=None, acodec="libopus", f="webm"
    )
    mock_stream.run.assert_called_once_with(quiet=True, overwrite_output=True)
    assert not source.exists()


@patch("bridge.audio_processor.ffmpeg")
def test_split_into_chunks_returns_sorted_chunks(mock_ffmpeg, tmp_path):
    audio = tmp_path / "audio.webm"
    audio.write_bytes(b"fake audio")
    chunks_dir = tmp_path / "chunks"
    chunks_dir.mkdir()

    mock_stream = MagicMock()
    mock_ffmpeg.input.return_value.output.return_value = mock_stream

    def create_fake_chunks(*args, **kwargs):
        for i in range(3):
            (chunks_dir / f"chunk_{i:03d}.webm").write_bytes(b"chunk")

    mock_stream.run.side_effect = create_fake_chunks

    chunks = split_into_chunks(audio, chunks_dir, chunk_duration=30)

    assert len(chunks) == 3
    assert [c.name for c in chunks] == ["chunk_000.webm", "chunk_001.webm", "chunk_002.webm"]
    mock_ffmpeg.input.return_value.output.assert_called_once_with(
        str(chunks_dir / "chunk_%03d.webm"),
        f="segment",
        segment_time=30,
        reset_timestamps=1,
        acodec="copy",
    )
