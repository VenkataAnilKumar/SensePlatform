###############################################################################
# Sense Gate — API Gateway Docker Image
###############################################################################

FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libffi-dev libssl-dev wget \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

COPY sense_gate/ ./sense_gate/
COPY alembic/ ./alembic/
COPY alembic.ini ./

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 3000

CMD ["uvicorn", "sense_gate.main:app", "--host", "0.0.0.0", "--port", "3000"]
