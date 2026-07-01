# Obraz serwisu wizyjnego dartscore (FastAPI HTTP/WebSocket).
# Uruchamiany jako osobny mikroserwis obok aplikacji Node.js — Node woła go po HTTP/WS.
FROM python:3.11-slim

# Szybszy, czystszy Python w kontenerze.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DARTSCORE_CALIBRATION=/data/calibration.json

WORKDIR /app

# Najpierw metadane projektu (lepsze cache warstw przy budowie).
COPY pyproject.toml README.md ./
COPY dartscore ./dartscore
COPY service ./service
COPY config ./config

# W kontenerze używamy OpenCV headless (bez libGL/GUI) + zależności serwisu (.[api]).
RUN pip install --upgrade pip \
    && pip install "opencv-python-headless>=4.8" \
    && pip install ".[api]"

# Katalog na trwały plik kalibracji (montowany jako wolumen w docker-compose).
RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 8000

# Nasłuch na wszystkich interfejsach, by usługa Node mogła się połączyć.
CMD ["uvicorn", "service.api:app", "--host", "0.0.0.0", "--port", "8000"]
