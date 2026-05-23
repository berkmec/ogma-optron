FROM python:3.11-slim

WORKDIR /app

# System deps for Pillow + onnxruntime
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libglib2.0-0 \
        libgl1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

EXPOSE 8000

# Default to listening on all interfaces inside the container;
# docker-compose.yml binds to 127.0.0.1 only on the host.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
