#!/usr/bin/env python3
"""
Setup script — clones SAM2 and ProPainter, downloads model weights.
Called by app.py on first run.
"""
import os
import subprocess
import sys

def setup():
    base_dir = os.path.dirname(os.path.abspath(__file__))

    # --- SAM2 ---
    sam2_dir = os.path.join(base_dir, "sam2")
    if not os.path.exists(sam2_dir):
        print("📦 Cloning SAM2...")
        subprocess.run(["git", "clone", "https://github.com/facebookresearch/sam2.git", sam2_dir], check=True)
        subprocess.run([sys.executable, "-m", "pip", "install", "-e", sam2_dir, "-q"], check=True)
    
    # Download weights
    ckpt_dir = os.path.join(sam2_dir, "checkpoints")
    ckpt_file = os.path.join(ckpt_dir, "sam2.1_hiera_large.pt")
    if not os.path.exists(ckpt_file):
        os.makedirs(ckpt_dir, exist_ok=True)
        print("⬇️  Downloading SAM2 weights...")
        subprocess.run([
            "wget", "-q", "-O", ckpt_file,
            "https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_large.pt"
        ], check=True)
    
    # --- ProPainter ---
    pp_dir = os.path.join(base_dir, "ProPainter")
    if not os.path.exists(pp_dir):
        print("📦 Cloning ProPainter...")
        subprocess.run(["git", "clone", "https://github.com/sczhou/ProPainter.git", pp_dir], check=True)
        req_file = os.path.join(pp_dir, "requirements.txt")
        if os.path.exists(req_file):
            subprocess.run([sys.executable, "-m", "pip", "install", "-r", req_file, "-q"], check=True)

    print("✅ Setup complete!")

if __name__ == "__main__":
    setup()
