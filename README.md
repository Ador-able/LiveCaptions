# LiveCaptions

LiveCaptions is a powerful, AI-driven video subtitle generation and translation service designed for high-quality, professional-grade subtitling. It leverages state-of-the-art models for speech recognition, speaker diarization, vocal isolation, and LLM-based translation to deliver "Netflix-standard" subtitles.

## Key Features

*   **Deep Learning Powered ASR**: Uses `faster-whisper` (Large-v3) for highly accurate transcription.
*   **Advanced Audio Processing**:
    *   **Vocal Isolation**: Integrates `Demucs` to separate vocals from loud background music, ensuring accuracy even in complex audio environments.
    *   **Speaker Diarization**: Uses `pyannote.audio` to distinguish between multiple speakers.
    *   **Voice Activity Detection (VAD)**: Strictly filters silence to prevent hallucinations.
*   **LLM Translation Agent**:
    *   **3-Step Translation**: Literal -> Reflect/Critique -> Free Translation (Polished).
    *   **Terminology Consistency**: Automatically extracts and adheres to a glossary of terms.
    *   **Context Awareness**: Translates based on the full context of the video.
*   **Netflix Standard Compliance**:
    *   Strict adherence to reading speed (CPS) and line length (CPL) limits.
    *   Intelligent segmentation for single-line subtitles (no dual lines).
*   **Task Management**:
    *   Supports pause, resume, and crash recovery.
    *   Real-time progress tracking and detailed logging.
*   **Deployment**:
    *   Single-container Docker deployment (Backend + Frontend + Redis + Workers).
    *   GPU Acceleration (supports NVIDIA 5090 and others).

## Prerequisites

*   **NVIDIA GPU**: Minimum 24GB VRAM recommended (e.g., RTX 3090/4090/5090) for full pipeline performance.
*   **Docker**: With NVIDIA Container Toolkit installed.
*   **OpenAI-compatible API Key**: For the LLM translation step (GPT-4, Claude, DeepSeek, etc.).

## Quick Start

1.  **Clone the Repository**:
    ```bash
    git clone https://github.com/Ador-able/LiveCaptions.git
    cd LiveCaptions
    ```

2.  **Environment Setup**:
    Create a `.env` file (optional, or pass env vars to Docker) or configure settings in the UI.

3.  **Run with Docker**:
    ```bash
    docker-compose up -d
    ```
    *   The service will be available at `http://localhost:8000`.
    *   Data will be persisted in the `./data` directory.

## Development

### Backend
The backend is built with **FastAPI** and uses **Celery** for background task processing.
*   `backend/main.py`: Entry point.
*   `backend/worker.py`: Celery worker configuration.
*   `backend/services/`: Core logic (ASR, LLM, Audio Processing).

### Frontend
The frontend is a **React** application (Vite + Tailwind CSS).
*   `frontend/src/`: Source code.

## License
[MIT](LICENSE)
