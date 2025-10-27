# app/Dockerfile
FROM python:3.13-slim

WORKDIR /app

# minimal system deps (ffmpeg not needed in API container)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
ENV PORT=8080
ENV JOBLIB_MULTIPROCESSING=0
EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
