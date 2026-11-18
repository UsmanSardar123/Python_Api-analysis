# Production Dockerfile for AI-Powered Website Link Analysis API
FROM python:3.12-slim

# Prevent Python from writing pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app

# Create non-root user for security best practices
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Install dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy application source
COPY app ./app

# Drop root privileges
USER appuser

EXPOSE 8000

# Run FastAPI via Uvicorn
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

