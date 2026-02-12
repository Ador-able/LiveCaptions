# Stage 1: Build Frontend
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
# We will copy package.json and install dependencies later when we have the code
# For now, we assume the frontend code is present during build
COPY frontend/ ./
# If package.json exists, install and build. If not, this step might fail or do nothing.
# To make this robust for initial setup, we can use a dummy build or skip if empty.
# But for a proper Dockerfile, we expect the source.
# I will leave this as a placeholder, assuming I will populate frontend before building.
RUN if [ -f package.json ]; then npm install && npm run build; fi

# Stage 2: Final Image
FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install System Dependencies
# redis-server: for task queue
# ffmpeg: for audio processing
# python3-pip, python3-venv: for backend
# git: for potential pip installs from git
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    python3-venv \
    ffmpeg \
    redis-server \
    supervisor \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set up Python alias
RUN ln -s /usr/bin/python3.10 /usr/bin/python

# Set working directory
WORKDIR /app

# Copy Backend Requirements
COPY backend/requirements.txt ./backend/requirements.txt

# Install Python Dependencies
# We use --no-cache-dir to keep image small
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r backend/requirements.txt && \
    python -m spacy download en_core_web_sm && \
    python -m spacy download zh_core_web_sm

# Pre-download models (Optional but recommended for faster startup)
# We can add a script here to download whisper models if needed,
# but usually faster-whisper downloads on first run.

# Copy Backend Code
COPY backend/ ./backend/

# Copy Frontend Build Artifacts
# We assume the frontend build output is in /app/frontend/dist
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Copy Supervisor Configuration
COPY docker/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Create directory for data persistence (mounted volume)
RUN mkdir -p /data

# Expose Ports
# 8000: FastAPI
EXPOSE 8000

# Environment Variables
ENV PYTHONPATH=/app
ENV CELERY_BROKER_URL=redis://localhost:6379/0
ENV CELERY_RESULT_BACKEND=redis://localhost:6379/0
ENV DATABASE_URL=sqlite:////data/tasks.db

# Start Supervisor
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
