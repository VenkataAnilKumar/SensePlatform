###############################################################################
# Sense Mind — Agent Engine Docker Image
###############################################################################

FROM python:3.11-slim AS base

# System deps for audio/video processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    libssl-dev \
    ffmpeg \
    wget \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ─────────────────────────────────────────────────────────────────────────────
# Install Python dependencies
# ─────────────────────────────────────────────────────────────────────────────
COPY pyproject.toml ./
COPY sense_mind/ ./sense_mind/

# CPU-only PyTorch keeps the image small; the lenses (YOLO) need it.
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Core deps + vision lenses (ultralytics) + default LLM/STT/TTS plugins
RUN pip install --no-cache-dir ".[vision,anthropic,deepgram,elevenlabs]"

# ─────────────────────────────────────────────────────────────────────────────
# Default startup — pool mode: agents are started per room via the REST API
# (POST /agents/start). Mount your own agent script and override CMD to run a
# single custom agent instead (see examples/).
# ─────────────────────────────────────────────────────────────────────────────
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SENSE_MIND_PORT=8080

EXPOSE 8080

CMD ["python", "-c", "from sense_mind import SenseRunner; SenseRunner().serve()"]
