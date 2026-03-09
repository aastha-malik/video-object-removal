# 🎬 Video Object Removal

> Upload a video, click on any object, and watch it disappear — seamlessly inpainted using state-of-the-art AI.

---

## ⚠️ Performance Notice

The ML pipeline is hosted on **Hugging Face Spaces (free tier, CPU only)**. Processing a video can take **several minutes** depending on length and resolution. This is a hardware limitation of the free plan — not a bug. For faster results, consider running the ML pipeline locally on a GPU.

---

## 🧠 How It Works

1. **Upload** a short video clip via the frontend
2. **Click** on the object you want to remove in the first frame
3. **SAM (Segment Anything Model)** segments the object and tracks it across all frames
4. **ProPainter / E2FGVI** inpaints the masked regions — filling in the background naturally
5. **Download** the cleaned output video

---

## 🏗️ Architecture

```
video-object-removal/
├── fe/               # Frontend (runs locally)
├── be/               # Backend API (runs locally)
└── ml_pipeline/      # ML inference (hosted on Hugging Face Spaces, CPU)
```

| Layer | Tech | Deployment |
|---|---|---|
| Frontend | TypeScript | Local |
| Backend | Python / FastAPI | Local |
| ML Pipeline | SAM + ProPainter/E2FGVI | Hugging Face Spaces (CPU) |

---

## 🚀 Getting Started

### Prerequisites

- Python 3.9+
- Node.js (for frontend)
- Git

---

### 1. Clone the repo

```bash
git clone https://github.com/aastha-malik/video-object-removal.git
cd video-object-removal
```

---

### 2. Run the Backend

```bash
cd be
pip install -r requirements.txt
python app.py
```

---

### 3. Run the Frontend

```bash
cd fe
npm install
npm run dev
```

---

### 4. ML Pipeline (Hugging Face Spaces)

The ML pipeline is already deployed on Hugging Face Spaces. The backend communicates with it automatically — no setup needed.

> 🐢 **Heads up:** Since the Space runs on a free CPU instance, inference is slow. A 5–10 second video may take **3–10 minutes** to process. Please be patient!

If you want to run the ML pipeline locally (much faster on GPU):

```bash
cd ml_pipeline
pip install -r requirements.txt
python app.py
```

Then update the backend config to point to your local ML endpoint.

---

## 🧩 Models Used

| Model | Role |
|---|---|
| [SAM — Segment Anything Model](https://github.com/facebookresearch/segment-anything) | Click-based object segmentation + frame tracking |
| [ProPainter](https://github.com/sczhou/ProPainter) / [E2FGVI](https://github.com/MCG-NKE/E2FGVI) | Video inpainting to fill removed regions |

---

## 📌 Limitations

- 🐢 **Slow on CPU** — free Hugging Face tier means long wait times
- 📹 Works best on **short clips** (under 15 seconds)
- 🎯 Click accuracy depends on the first frame — choose a clear, unoccluded object
- Fast-moving or heavily occluded objects may not track perfectly

---

## 🛣️ Roadmap

- [ ] GPU-backed inference for faster processing
- [ ] Multi-object selection support
- [ ] Drag-to-draw mask fallback
- [ ] Progress bar during processing

---

## 📄 License

This project is open source. See [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgements

- [Meta AI — Segment Anything](https://github.com/facebookresearch/segment-anything)
- [ProPainter](https://github.com/sczhou/ProPainter)
- [E2FGVI](https://github.com/MCG-NKE/E2FGVI)
- [Hugging Face Spaces](https://huggingface.co/spaces) for free model hosting
