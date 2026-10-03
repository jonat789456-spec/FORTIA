FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CAPTURE_MODE=web \
    HOST=0.0.0.0 \
    PORT=8000

WORKDIR /app
COPY requirements/base.txt ./requirements/base.txt
RUN pip install --no-cache-dir -r requirements/base.txt
COPY app ./app
COPY config ./config
COPY artifacts/registry.json ./artifacts/registry.json
COPY artifacts/baselines ./artifacts/baselines
COPY artifacts/multimodal ./artifacts/multimodal

EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host ${HOST} --port ${PORT}"]
