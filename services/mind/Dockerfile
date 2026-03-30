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

# Install core deps (no vision lenses by default — add [vision] for YOLO)
RUN pip install --no-cache-dir -e ".[anthropic,deepgram,elevenlabs]"

# ─────────────────────────────────────────────────────────────────────────────
# Copy application source
# ─────────────────────────────────────────────────────────────────────────────
COPY sense_mind/ ./sense_mind/

# ─────────────────────────────────────────────────────────────────────────────
# Default startup — runs the basic contact center agent example
# Override CMD or mount your own agent at /app/agent.py
# ─────────────────────────────────────────────────────────────────────────────
COPY examples/ ./examples/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SENSE_MIND_PORT=8080

EXPOSE 8080

CMD ["python", "examples/contact_center/agent.py"]
