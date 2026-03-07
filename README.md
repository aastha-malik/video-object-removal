---
title: Video Object Remover
emoji: 🎬
colorFrom: green
colorTo: blue
sdk: gradio
sdk_version: 5.12.0
app_file: app.py
pinned: false
license: mit
---

# 🎬 Video Object Remover

Remove any object from a video using **SAM2** (Segment Anything Model 2) + **ProPainter** (video inpainting).

## How it works
1. Upload a video
2. Click on the first frame to select objects you want removed
3. SAM2 tracks those objects across all frames
4. ProPainter fills in the gaps seamlessly
5. Download your clean video!

## Tech Stack
- **SAM2** — Meta's Segment Anything Model 2 for object tracking
- **ProPainter** — State-of-the-art video inpainting
- **Gradio** — Web UI
