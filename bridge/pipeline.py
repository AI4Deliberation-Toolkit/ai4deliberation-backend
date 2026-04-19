import shutil
import tempfile
from pathlib import Path

from bridge.audio_processor import extract_audio, get_duration, inspect_file, split_into_chunks
from bridge.config import get_project_id
from bridge.dembrane_client import finish_conversation, initiate_conversation, upload_chunk


async def process_recording(
    file_path: Path,
    event_id: str,
    breakout_id: str,
    timestamp: str,
) -> None:
    tmp_dir = file_path.parent

    try:
        project_id = get_project_id(event_id)

        # [1] Inspect file — extract audio if video
        file_type = inspect_file(file_path)
        if file_type == "video":
            audio_path = tmp_dir / "audio.webm"
            try:
                extract_audio(file_path, audio_path)
                # file_path deleted by extract_audio
            except Exception:
                # DECISION NEEDED: ffmpeg failed to extract audio from the source file.
                # Options: return error, notify Frankly, retain source for retry?
                # See: docs/superpowers/specs/2026-04-19-bridge-audio-pipeline-design.md
                raise
        else:
            audio_path = file_path

        # [2] Detect mode by duration
        duration = get_duration(audio_path)

        # [3] Initiate dembrane conversation
        conversation_id = await initiate_conversation(project_id, f"{event_id} / {breakout_id}")

        # [4] Upload chunks
        if duration > 60:
            chunks_dir = tmp_dir / "chunks"
            chunks_dir.mkdir()
            chunks = split_into_chunks(audio_path, chunks_dir, chunk_duration=30)
            for chunk in chunks:
                try:
                    await upload_chunk(conversation_id, chunk, timestamp)
                    chunk.unlink()
                except Exception:
                    # DECISION NEEDED: chunk upload to dembrane failed.
                    # Option A (Phase 1): abort remaining chunks.
                    # Option C (deferred): retain audio and resume from this chunk —
                    #   requires persistent state and legal sign-off on audio retention.
                    # See: docs/superpowers/specs/2026-04-19-bridge-audio-pipeline-design.md
                    raise
            audio_path.unlink()
        else:
            # Single chunk — audio file IS the chunk
            try:
                await upload_chunk(conversation_id, audio_path, timestamp)
                audio_path.unlink()
            except Exception:
                # DECISION NEEDED: same as above.
                raise

        # [5] Finish conversation
        await finish_conversation(conversation_id)

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
