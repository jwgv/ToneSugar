# analyzer/Dockerfile - Lambda container image (Python)
# Use a standard Python base but include the AWS Lambda Runtime Interface Client (RIC)
# so the image is Lambda-compatible even without the AWS base image.
FROM python:3.12-slim

WORKDIR /var/task

# System libs needed by librosa/soundfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install (include awslambdaric for Lambda runtime)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir awslambdaric

# Copy handler
COPY handler.py .

# Environment tweaks to avoid numba caching issues in Lambda and ensure temp dirs are writable
ENV NUMBA_DISABLE_CACHING=1 \
    NUMBA_CACHE_DIR=/tmp \
    JOBLIB_TEMP_FOLDER=/tmp \
    JOBLIB_MULTIPROCESSING=0

# Set the Lambda entrypoint to the Runtime Interface Client
ENTRYPOINT ["python", "-m", "awslambdaric"]
# The handler stays as CMD so AWS can override if needed
CMD ["handler.handler"]
