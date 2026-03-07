"""FastAPI backend for Video Object Remover."""
import asyncio
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
    """Upload a local video file to the HF Space and return the remote file path."""
    filename = Path(video_path).name
    with open(video_path, "rb") as f:
        resp = await client.post(
            f"{HF_API_URL}/upload",
            files={"files": (filename, f, "video/mp4")},
            timeout=120,
        )
    resp.raise_for_status()
    paths = resp.json()
    return paths[0]  # e.g. "tmp/gradio/abc123/video.mp4"


async def stream_hf_progress(client: httpx.AsyncClient, remote_path: str, coords_json: str, session_hash: str):
    """
    Join the Gradio queue and yield SSE event dicts.
    fn_index=3 corresponds to remove_btn.click(on_remove, ...) in app.py.
    Gradio 5 requires fn_index; api_name is not supported in queue/join.
    """
    # Gradio 5 gr.Video expects VideoData: {"video": FileData, "subtitles": null}
    join_payload = {
        "data": [
            {
                "video": {
                    "path": remote_path,
                    "meta": {"_type": "gradio.FileData"},
                },
                "subtitles": None,
            },
            coords_json,
        ],
        "fn_index": 3,
        "session_hash": session_hash,
    }
    resp = await client.post(f"{HF_API_URL}/queue/join", json=join_payload, timeout=30)
    resp.raise_for_status()

    async with client.stream(
        "GET",
        f"{HF_API_URL}/queue/data",
        params={"session_hash": session_hash},
        timeout=600,
    ) as stream:
        async for line in stream.aiter_lines():
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if not payload:
                continue
            event = json.loads(payload)
            log.info("SSE event [%s]: %s", event.get("msg"), json.dumps(event)[:300])
            yield event
            if event.get("msg") in ("process_completed", "error"):
                return


@app.websocket("/ws/process")
async def process_video(websocket: WebSocket):
    await websocket.accept()
    try:
        data = await websocket.receive_json()
        session_id = data.get("session_id")
        coordinates = data.get("coordinates", [])

        session = sessions.get(session_id)
        if not session:
            await websocket.send_json({"error": "Session not found"})
            return

        video_path = session["video_path"]
        coords_json = json.dumps(coordinates)
        session_hash = str(uuid.uuid4())[:12]

        await websocket.send_json({"progress": 5, "message": "Uploading video to ML pipeline..."})

        async with httpx.AsyncClient(follow_redirects=True) as client:
            # Step 1: Upload video to HF Space
            remote_path = await upload_file_to_hf(client, video_path)
            await websocket.send_json({"progress": 12, "message": "Video uploaded, starting ML processing..."})

            # Step 2: Stream SSE events from the Gradio queue
            async for event in stream_hf_progress(client, remote_path, coords_json, session_hash):
                msg = event.get("msg")

                if msg == "estimation":
                    rank = event.get("rank", 0)
                    if rank and rank > 0:
                        await websocket.send_json({
                            "progress": 15,
                            "message": f"Waiting in queue (position {rank})...",
                        })

                elif msg == "process_starts":
                    await websocket.send_json({"progress": 20, "message": "Processing started..."})

                elif msg == "progress":
                    for p in event.get("progress_data", []):
                        idx = p.get("index", 0)
                        length = p.get("length") or 1
                        raw = p.get("progress")
                        pct = int(float(raw) * 100) if raw is not None else int(idx / length * 100)
                        # Map ML progress (0-100) to 20-95 range
                        display_pct = 20 + int(pct * 0.75)
                        desc = p.get("desc") or "Processing..."
                        await websocket.send_json({"progress": display_pct, "message": desc})

                elif msg == "process_generating":
                    # Intermediate output – ignore
                    pass

                elif msg == "process_completed":
                    log.info("process_completed event: %s", json.dumps(event)[:1000])
                    output = event.get("output", {})

                    # Gradio surfaces errors two ways:
                    # 1. output["error"] field (top-level failure)
                    # 2. output["data"][0] is None with message in output["data"][1]
                    if output.get("error"):
                        await websocket.send_json({"error": output["error"]})
                        return

                    output_data = output.get("data", [])
                    if not output_data or output_data[0] is None:
                        # Extract the status message — it usually contains the error text
                        status_msg = output_data[1] if len(output_data) > 1 else None
                        err_text = str(status_msg) if status_msg else "ML pipeline returned no output"
                        await websocket.send_json({"error": err_text})
                        return

                    # output_data[0] is VideoData: {"video": FileData, "subtitles": ...}
                    result_video_data = output_data[0]
                    status_msg = output_data[1] if len(output_data) > 1 else "Done!"

                    # Unwrap VideoData → FileData
                    if isinstance(result_video_data, dict) and "video" in result_video_data:
                        result_file = result_video_data["video"]
                    else:
                        result_file = result_video_data

                    # Resolve the result video URL from FileData
                    if isinstance(result_file, dict):
                        file_url = result_file.get("url") or result_file.get("path", "")
                    else:
                        file_url = str(result_file)

                    # If it's a relative path, build the full URL
                    if file_url and not file_url.startswith("http"):
                        file_url = f"{HF_API_URL}/file={file_url}"

                    # Download the result video locally
                    await websocket.send_json({"progress": 97, "message": "Downloading result..."})
                    result_path = RESULT_DIR / f"{session_id}_result.mp4"
                    async with client.stream("GET", file_url, timeout=120) as dl:
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

                elif msg == "error":
                    err = event.get("output") or "Unknown error from ML pipeline"
                    await websocket.send_json({"error": str(err)})
                    return

    except httpx.HTTPStatusError as e:
        await websocket.send_json({"error": f"HF Space API error: {e.response.status_code}"})
    except Exception as e:
        await websocket.send_json({"error": str(e)})
    finally:
        await websocket.close()


@app.get("/api/result/{session_id}")
async def get_result(session_id: str):
    session = sessions.get(session_id)
    if not session or "result_path" not in session:
        raise HTTPException(status_code=404, detail="Result not found")
    return FileResponse(session["result_path"], media_type="video/mp4", filename="result.mp4")
