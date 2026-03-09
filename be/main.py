"""FastAPI backend for Video Object Remover."""
import base64
import json
import logging
import os
import tempfile
import uuid
from pathlib import Path

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

import cv2
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

load_dotenv()

HF_SPACE_URL = os.getenv("HF_SPACE_URL", "https://aastha-malik-video-object-remover.hf.space").rstrip("/")
# Gradio 5 uses /gradio_api prefix for all API endpoints
HF_API_URL = f"{HF_SPACE_URL}/gradio_api"

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

sessions: dict = {}
UPLOAD_DIR = Path(tempfile.gettempdir()) / "video_remover_uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
RESULT_DIR = Path(tempfile.gettempdir()) / "video_remover_results"
RESULT_DIR.mkdir(exist_ok=True)


@app.post("/api/upload")
async def upload_video(file: UploadFile = File(...)):
    session_id = str(uuid.uuid4())
    suffix = Path(file.filename or "video.mp4").suffix or ".mp4"
    video_path = UPLOAD_DIR / f"{session_id}{suffix}"

    content = await file.read()
    with open(video_path, "wb") as f:
        f.write(content)

    cap = cv2.VideoCapture(str(video_path))
    ret, frame = cap.read()
    cap.release()

    if not ret:
        raise HTTPException(status_code=400, detail="Could not read video file")

    _, buffer = cv2.imencode(".jpg", frame)
    frame_b64 = base64.b64encode(buffer).decode()
    h, w = frame.shape[:2]

    sessions[session_id] = {"video_path": str(video_path)}

    return {
        "session_id": session_id,
        "frame": f"data:image/jpeg;base64,{frame_b64}",
        "width": w,
        "height": h,
    }


async def upload_file_to_hf(client: httpx.AsyncClient, video_path: str) -> str:
    """Upload local video to HF Space, return remote path."""
    filename = Path(video_path).name
    with open(video_path, "rb") as f:
        resp = await client.post(
            f"{HF_API_URL}/upload",
            files={"files": (filename, f, "video/mp4")},
            timeout=120,
        )
    resp.raise_for_status()
    return resp.json()[0]  # e.g. "tmp/gradio/abc123/video.mp4"


async def call_on_remove(client: httpx.AsyncClient, remote_path: str, coords_json: str):
    """
    Call /gradio_api/call/on_remove (Gradio 5 named API).
    Returns an event_id to poll for results.
    Input: FileData (plain, no VideoData wrapper) + coords_json string.
    """
    payload = {
        "data": [
            {
                "path": remote_path,
                "meta": {"_type": "gradio.FileData"},
            },
            coords_json,
        ]
    }
    log.info("Calling /on_remove with path=%s coords=%s", remote_path, coords_json[:200])
    resp = await client.post(
        f"{HF_API_URL}/call/on_remove",
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    event_id = resp.json()["event_id"]
    log.info("Got event_id: %s", event_id)
    return event_id


async def stream_on_remove_result(client: httpx.AsyncClient, event_id: str, websocket: WebSocket, _hb: int = 0):
    """
    Stream SSE results from /gradio_api/call/on_remove/{event_id}.
    Gradio 5 named API sends:
      event: heartbeat   data: null   (keep-alive, ~every 15s while processing)
      event: complete    data: [video_output, status_text]
      event: error       data: "error message"
    """
    event_type = None
    heartbeat_count = 0
    steps = ["Extracting frames...", "SAM2: Loading model...", "SAM2: Tracking objects...",
             "ProPainter: Inpainting...", "Finalizing video..."]
    async with client.stream(
        "GET",
        f"{HF_API_URL}/call/on_remove/{event_id}",
        timeout=1800,
    ) as stream:
        async for line in stream.aiter_lines():
            if line.startswith("event:"):
                event_type = line[6:].strip()
                log.info("SSE event: %s", event_type)
            elif line.startswith("data:"):
                payload = line[5:].strip()
                if not payload:
                    continue
                parsed = json.loads(payload)
                if event_type == "heartbeat":
                    # Pipeline is running — show cycling progress messages
                    heartbeat_count += 1
                    step_msg = steps[min(heartbeat_count // 3, len(steps) - 1)]
                    pct = min(20 + heartbeat_count * 2, 90)
                    await websocket.send_json({"progress": pct, "message": step_msg})
                elif event_type == "complete":
                    log.info("SSE complete data: %s", str(parsed)[:300])
                    yield parsed
                    return
                elif event_type == "error":
                    raise Exception(f"HF Space error: {parsed}")


@app.websocket("/ws/process")
async def process_video(websocket: WebSocket):
    await websocket.accept()
    try:
        data = await websocket.receive_json()
        session_id = data.get("session_id")
        coordinates = data.get("coordinates", [])
        log.info("WS received session=%s coords_count=%d", session_id, len(coordinates))

        session = sessions.get(session_id)
        if not session:
            await websocket.send_json({"error": "Session not found"})
            return

        if not coordinates:
            await websocket.send_json({"error": "No coordinates provided"})
            return

        video_path = session["video_path"]
        coords_json = json.dumps(coordinates)

        await websocket.send_json({"progress": 5, "message": "Uploading video to ML pipeline..."})

        async with httpx.AsyncClient(follow_redirects=True, timeout=httpx.Timeout(60, read=1800)) as client:
            # Step 0: Wake the HF Space (free tier hibernates after inactivity)
            await websocket.send_json({"progress": 3, "message": "Waking up ML pipeline (may take ~15s)..."})
            try:
                await client.get(HF_SPACE_URL, timeout=30)
            except Exception:
                pass  # ignore wake-up errors, proceed anyway

            # Step 1: Upload video to HF Space
            remote_path = await upload_file_to_hf(client, video_path)
            log.info("Uploaded to HF: %s", remote_path)
            await websocket.send_json({"progress": 12, "message": "Video uploaded, starting ML processing..."})

            # Step 2: Call the named API endpoint
            event_id = await call_on_remove(client, remote_path, coords_json)
            await websocket.send_json({"progress": 20, "message": "ML processing started (SAM2 + ProPainter)..."})

            # Step 3: Stream the result (heartbeats keep connection alive while SAM2+ProPainter runs)
            heartbeat_count = 0
            async for result_data in stream_on_remove_result(client, event_id, websocket, heartbeat_count):
                log.info("Result data: %s", json.dumps(result_data)[:500])

                # result_data is a list: [video_output, status_text]
                if not isinstance(result_data, list) or len(result_data) < 2:
                    await websocket.send_json({"error": f"Unexpected result format: {result_data}"})
                    return

                result_file_data = result_data[0]  # FileData dict or None
                status_msg = result_data[1] or ""

                if result_file_data is None:
                    err = str(status_msg) if status_msg else "ML pipeline returned no output"
                    await websocket.send_json({"error": err})
                    return

                # Resolve download URL from FileData
                if isinstance(result_file_data, dict):
                    file_url = result_file_data.get("url") or result_file_data.get("path", "")
                else:
                    file_url = str(result_file_data)

                if file_url and not file_url.startswith("http"):
                    file_url = f"{HF_API_URL}/file={file_url}"

                log.info("Downloading result from: %s", file_url)
                await websocket.send_json({"progress": 95, "message": "Downloading result video..."})

                result_path = RESULT_DIR / f"{session_id}_result.mp4"
                async with client.stream("GET", file_url, timeout=300) as dl:
                    dl.raise_for_status()
                    with open(result_path, "wb") as out:
                        async for chunk in dl.aiter_bytes(8192):
                            out.write(chunk)

                sessions[session_id]["result_path"] = str(result_path)
                await websocket.send_json({
                    "done": True,
                    "progress": 100,
                    "message": str(status_msg),
                    "result_url": f"/api/result/{session_id}",
                })
                return

            await websocket.send_json({"error": "No result received from ML pipeline"})

    except httpx.HTTPStatusError as e:
        log.error("HTTP error: %s %s", e.response.status_code, e.response.text[:200])
        await websocket.send_json({"error": f"HF Space API error: {e.response.status_code} — {e.response.text[:200]}"})
    except Exception as e:
        log.exception("Unexpected error")
        await websocket.send_json({"error": str(e)})
    finally:
        await websocket.close()


@app.get("/api/result/{session_id}")
async def get_result(session_id: str):
    session = sessions.get(session_id)
    if not session or "result_path" not in session:
        raise HTTPException(status_code=404, detail="Result not found")
    return FileResponse(session["result_path"], media_type="video/mp4", filename="result.mp4")
