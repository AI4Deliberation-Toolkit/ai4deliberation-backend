import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from bridge.config import HMAC_SECRET
from bridge.hmac_auth import verify_hmac
from bridge.pipeline import process_recording

router = APIRouter()


@router.post("/recordings/incoming", status_code=202)
async def receive_recording(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    event_id: str = Form(...),
    breakout_id: str = Form(...),
    timestamp: str = Form(...),
    hmac_signature: str = Form(...),
) -> Response:
    tmp_dir = Path(tempfile.mkdtemp())
    file_ext = Path(file.filename or "recording.bin").suffix or ".bin"
    file_path = tmp_dir / f"recording{file_ext}"

    # Stream file to disk in 1 MB chunks — avoids loading a large file into memory
    with open(file_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            f.write(chunk)

    if not verify_hmac(event_id, breakout_id, timestamp, file_path, hmac_signature, HMAC_SECRET):
        shutil.rmtree(tmp_dir)
        raise HTTPException(status_code=400, detail="Invalid HMAC signature")

    background_tasks.add_task(process_recording, file_path, event_id, breakout_id, timestamp)
    return Response(status_code=202)
