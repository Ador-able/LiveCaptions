FROM nvidia/cuda:12.8.0-base-ubuntu24.04

# Avoid interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install Python 3.12 and dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    ffmpeg \
    git \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Upgrade pip
RUN python3 -m pip install --upgrade pip --break-system-packages

<<<<<<< HEAD
# Install dependencies
COPY backend/requirements.txt .
RUN python3 -m pip install --break-system-packages -r requirements.txt
=======
# Install Python Dependencies
# We use --no-cache-dir to keep image small
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r backend/requirements.txt && \
    python -m spacy download en_core_web_sm && \
    python -m spacy download zh_core_web_sm
>>>>>>> origin/jules-alignment-segmentation-13533857260951222738

# Download Spacy models
RUN python3 -m spacy download zh_core_web_sm --break-system-packages
RUN python3 -m spacy download en_core_web_sm --break-system-packages

# Copy code
COPY . .

# Environment
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

CMD ["/usr/bin/supervisord", "-c", "/app/docker/supervisord.conf"]
