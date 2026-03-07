"""
🎬 Video Object Remover — SAM2 + ProPainter
HuggingFace Spaces deployment
"""
import gradio as gr
import os
import sys
import json
import subprocess
import tempfile
import numpy as np
import cv2

# ─── Setup on first run ───
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAM2_DIR = os.path.join(BASE_DIR, "sam2")
PROPAINTER_DIR = os.path.join(BASE_DIR, "ProPainter")

# Run setup if models aren't downloaded yet
if not os.path.exists(os.path.join(SAM2_DIR, "checkpoints", "sam2.1_hiera_large.pt")):
    from setup_models import setup
    setup()

# Add SAM2 to path
if SAM2_DIR not in sys.path:
    sys.path.insert(0, SAM2_DIR)


# ─── Helper Functions ───

def extract_frame(video_path):
    """Extract first frame from video for object selection."""
    if not video_path:
        return None
    cap = cv2.VideoCapture(video_path)
    ret, frame = cap.read()
    cap.release()
    if ret:
        return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    return None


def remove_objects(video_path, coords_json, progress=gr.Progress()):
    """Main pipeline: video + coordinates → result video."""
    try:
        if not video_path:
            return None, "❌ No video provided!"

        coords = json.loads(coords_json) if coords_json else []
        if not coords:
            return None, "❌ No coordinates provided! Click on the frame to select objects."

        progress(0.05, desc="Setting up...")

        work_dir = tempfile.mkdtemp(prefix="objremover_")
        frames_dir = os.path.join(work_dir, "frames")
        masks_dir = os.path.join(work_dir, "masks")
        output_dir = os.path.join(work_dir, "output")

        for d in [frames_dir, masks_dir, output_dir]:
            os.makedirs(d, exist_ok=True)

        # ─── STEP 1: Extract frames ───
        progress(0.1, desc="Extracting frames...")
        subprocess.run([
            'ffmpeg', '-i', video_path, '-q:v', '2',
            os.path.join(frames_dir, '%05d.jpg'),
            '-hide_banner', '-loglevel', 'quiet'
        ], check=True)

        num_frames = len([f for f in os.listdir(frames_dir) if f.endswith('.jpg')])
        print(f"📁 Extracted {num_frames} frames")
        if num_frames == 0:
            return None, "❌ Could not extract frames!"

        # ─── STEP 2: SAM2 tracking ───
        progress(0.2, desc="SAM2: Loading model...")
        
        import torch
        from hydra.core.global_hydra import GlobalHydra
        from hydra import initialize_config_dir
        from sam2.build_sam import build_sam2_video_predictor

        os.chdir(SAM2_DIR)
        GlobalHydra.instance().clear()

        with initialize_config_dir(
            config_dir=os.path.join(SAM2_DIR, "sam2", "configs", "sam2.1"),
            version_base=None
        ):
            predictor = build_sam2_video_predictor(
                "sam2.1_hiera_l.yaml",
                os.path.join(SAM2_DIR, "checkpoints", "sam2.1_hiera_large.pt"),
                device="cuda" if torch.cuda.is_available() else "cpu"
            )

        progress(0.3, desc="SAM2: Initializing tracker...")
        inference_state = predictor.init_state(video_path=frames_dir)

        obj_id = 1
        for coord in coords:
            if coord.get('type') == 'point':
                predictor.add_new_points_or_box(
                    inference_state=inference_state, frame_idx=0, obj_id=obj_id,
                    points=np.array([[coord['x'], coord['y']]], dtype=np.float32),
                    labels=np.array([1], dtype=np.int32)
                )
                print(f"📍 Point ({coord['x']}, {coord['y']}) → obj {obj_id}")
            elif coord.get('type') == 'box':
                predictor.add_new_points_or_box(
                    inference_state=inference_state, frame_idx=0, obj_id=obj_id,
                    box=np.array([coord['x1'], coord['y1'], coord['x2'], coord['y2']], dtype=np.float32)
                )
                print(f"▭ Box ({coord['x1']},{coord['y1']})→({coord['x2']},{coord['y2']}) → obj {obj_id}")
            obj_id += 1

        progress(0.4, desc="SAM2: Tracking objects across frames...")
        video_segments = {}
        for frame_idx, object_ids, masks in predictor.propagate_in_video(inference_state):
            video_segments[frame_idx] = {
                oid: masks[i].cpu().numpy() for i, oid in enumerate(object_ids)
            }

        print(f"🔍 Tracked {len(video_segments)} frames")

        progress(0.5, desc="Saving masks...")
        for frame_idx, segments in video_segments.items():
            combined = None
            for oid, mask_data in segments.items():
                binary = (mask_data[0] > 0).astype(np.uint8) * 255
                combined = binary if combined is None else np.maximum(combined, binary)
            cv2.imwrite(os.path.join(masks_dir, f"{frame_idx+1:05d}.png"), combined)

        # ─── STEP 3: ProPainter inpainting ───
        progress(0.6, desc="ProPainter: Inpainting...")
        os.chdir(PROPAINTER_DIR)
        sample = cv2.imread(os.path.join(frames_dir, '00001.jpg'))
        h, w = sample.shape[:2]

        subprocess.run([
            sys.executable, 'inference_propainter.py',
            '--video', frames_dir, '--mask', masks_dir,
            '--output', output_dir, '--height', str(h), '--width', str(w)
        ], check=True)

        progress(0.9, desc="Finalizing video...")

        # ─── STEP 4: Find output ───
        inpaint_path = None
        for root, dirs, files in os.walk(output_dir):
            for f in files:
                if 'inpaint' in f and f.endswith('.mp4'):
                    inpaint_path = os.path.join(root, f)
                    break

        if not inpaint_path:
            return None, "❌ ProPainter produced no output!"

        final_path = os.path.join(tempfile.gettempdir(), "result_video.mp4")
        subprocess.run([
            'ffmpeg', '-i', inpaint_path,
            '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
            final_path, '-y', '-hide_banner', '-loglevel', 'quiet'
        ], check=True)

        size_mb = os.path.getsize(final_path) / (1024 * 1024)
        msg = f"✅ Removed {len(coords)} object(s) across {num_frames} frames ({size_mb:.1f} MB)"
        print(msg)

        progress(1.0, desc="Done!")
        return final_path, msg

    except Exception as e:
        import traceback
        traceback.print_exc()
        return None, f"❌ Error: {str(e)}"


# ─── Custom CSS ───
custom_css = """
.gradio-container {
    max-width: 1200px !important;
    margin: auto !important;
}
#header {
    text-align: center;
    margin-bottom: 1rem;
}
#header h1 {
    font-size: 2.2rem;
    margin-bottom: 0.3rem;
}
#header p {
    opacity: 0.7;
    font-size: 1.05rem;
}
.remove-btn {
    font-size: 1.1rem !important;
    padding: 12px 32px !important;
}
"""

# ─── BUILD UI ───
with gr.Blocks(
    title="Video Object Remover",
    theme=gr.themes.Base(primary_hue="emerald"),
    css=custom_css
) as demo:

    gr.HTML("""
        <div id="header">
            <h1>🎬 Video Object Remover</h1>
            <p>Upload a video → click on objects to remove → hit Remove!</p>
        </div>
    """)

    with gr.Row(equal_height=True):
        # ─── Left: Input ───
        with gr.Column(scale=1):
            video_input = gr.Video(label="📁 Upload Video")
            frame_preview = gr.Image(
                label="👆 Click on the object to remove",
                interactive=True, type="numpy"
            )
            coords_display = gr.Textbox(
                label="📍 Selected Coordinates",
                lines=3, interactive=True,
                placeholder="Click on the frame above — coordinates appear here"
            )
            with gr.Row():
                clear_btn = gr.Button("🔄 Clear Selections", variant="secondary")
                remove_btn = gr.Button(
                    "🗑️ Remove Objects", variant="primary",
                    elem_classes=["remove-btn"]
                )

        # ─── Right: Output ───
        with gr.Column(scale=1):
            result_video = gr.Video(label="🎬 Result Video")
            status_text = gr.Textbox(label="Status", interactive=False)

    gr.HTML("""
        <div style="text-align:center; margin-top:1.5rem; opacity:0.5; font-size:0.85rem;">
            Powered by <strong>SAM2</strong> (Meta) + <strong>ProPainter</strong> (sczhou)
        </div>
    """)

    # ─── State ───
    coord_state = gr.State([])
    original_frame = gr.State(None)

    # ─── Event Handlers ───
    def on_video_upload(video):
        frame = extract_frame(video)
        return frame, frame, "[]", []

    def on_frame_click(frame, orig_frame, evt: gr.SelectData, current_coords):
        if frame is None:
            return frame, "[]", []

        x, y = evt.index[0], evt.index[1]
        coord = {"type": "point", "x": int(x), "y": int(y), "frame_time": 0.0}

        if current_coords is None:
            current_coords = []
        current_coords.append(coord)

        # Redraw all markers on the ORIGINAL frame (avoid marker buildup)
        if orig_frame is not None:
            marked = orig_frame.copy()
        else:
            marked = frame.copy()

        for i, c in enumerate(current_coords):
            cx, cy = c['x'], c['y']
            # Green circle with number label
            cv2.circle(marked, (cx, cy), 10, (0, 200, 80), 2)
            cv2.circle(marked, (cx, cy), 4, (0, 255, 100), -1)
            cv2.putText(marked, str(i + 1), (cx + 12, cy + 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 100), 2)

        return marked, json.dumps(current_coords, indent=2), current_coords

    def on_clear(orig_frame):
        if orig_frame is not None:
            return orig_frame, "[]", []
        return None, "[]", []

    def on_remove(video, coords_json):
        return remove_objects(video, coords_json)

    # ─── Wire Events ───
    video_input.change(
        on_video_upload, [video_input],
        [frame_preview, original_frame, coords_display, coord_state]
    )
    frame_preview.select(
        on_frame_click, [frame_preview, original_frame, coord_state],
        [frame_preview, coords_display, coord_state]
    )
    clear_btn.click(
        on_clear, [original_frame],
        [frame_preview, coords_display, coord_state]
    )
    remove_btn.click(
        on_remove, [video_input, coords_display],
        [result_video, status_text]
    )


# ─── Launch ───
if __name__ == "__main__":
    demo.launch(allowed_paths=["/tmp"])
