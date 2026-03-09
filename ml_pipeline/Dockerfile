FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
    git ffmpeg wget libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

RUN git clone https://github.com/facebookresearch/sam2.git /app/sam2 && \
    cd /app/sam2 && pip install -e . -q

RUN git clone https://github.com/sczhou/ProPainter.git /app/ProPainter && \
    pip install -r /app/ProPainter/requirements.txt -q

RUN pip install --no-cache-dir "gradio>=5.20.0" "gradio-client>=1.7.0" huggingface_hub

RUN mkdir -p /app/sam2/checkpoints && \
    wget -q -O /app/sam2/checkpoints/sam2.1_hiera_large.pt \
    https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_large.pt

COPY app.py .
COPY setup_models.py .
COPY requirements.txt .

EXPOSE 7860

CMD ["python", "app.py"]