FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libffi-dev libssl-dev wget \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

COPY sense_wire/ ./sense_wire/

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

EXPOSE 3001

CMD ["uvicorn", "sense_wire.main:app", "--host", "0.0.0.0", "--port", "3001"]
