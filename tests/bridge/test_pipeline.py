import shutil
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest
from bridge.pipeline import process_recording


@pytest.fixture
def tmp_recording(tmp_path):
    f = tmp_path / "rec.mp4"
    f.write_bytes(b"fake video")
    return f


@patch("bridge.pipeline.inspect_file", return_value="video")
@patch("bridge.pipeline.extract_audio")
@patch("bridge.pipeline.get_duration", return_value=120.0)
@patch("bridge.pipeline.split_into_chunks")
@patch("bridge.pipeline.initiate_conversation", new_callable=AsyncMock, return_value="conv-1")
@patch("bridge.pipeline.upload_chunk", new_callable=AsyncMock)
@patch("bridge.pipeline.finish_conversation", new_callable=AsyncMock)
async def test_whole_video_file_happy_path(
    mock_finish, mock_upload, mock_initiate, mock_split,
    mock_duration, mock_extract, mock_inspect, tmp_path
):
    rec = tmp_path / "rec.mp4"
    rec.write_bytes(b"fake video")

    audio = tmp_path / "audio.webm"
    chunk1 = tmp_path / "chunks" / "chunk_000.webm"
    chunk2 = tmp_path / "chunks" / "chunk_001.webm"

    def fake_extract(src, dst):
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(b"audio")

    def fake_split(audio_path, out_dir, chunk_duration):
        out_dir.mkdir(parents=True, exist_ok=True)
        chunk1.parent.mkdir(parents=True, exist_ok=True)
        chunk1.write_bytes(b"c1")
        chunk2.write_bytes(b"c2")
        return [chunk1, chunk2]

    mock_extract.side_effect = fake_extract
    mock_split.side_effect = fake_split

    await process_recording(rec, "ev-1", "br-1", "proj-abc", "2026-04-19T10:00:00Z")

    mock_initiate.assert_called_once_with("proj-abc", "ev-1 / br-1")
    assert mock_upload.call_count == 2
    mock_finish.assert_called_once_with("conv-1")


@patch("bridge.pipeline.inspect_file", return_value="audio")
@patch("bridge.pipeline.get_duration", return_value=25.0)
@patch("bridge.pipeline.initiate_conversation", new_callable=AsyncMock, return_value="conv-1")
@patch("bridge.pipeline.upload_chunk", new_callable=AsyncMock)
@patch("bridge.pipeline.finish_conversation", new_callable=AsyncMock)
async def test_single_audio_chunk_skips_split(
    mock_finish, mock_upload, mock_initiate,
    mock_duration, mock_inspect, tmp_path
):
    rec = tmp_path / "rec.webm"
    rec.write_bytes(b"short audio")

    await process_recording(rec, "ev-1", "br-1", "proj-abc", "2026-04-19T10:00:00Z")

    mock_upload.assert_called_once()
    mock_finish.assert_called_once_with("conv-1")
