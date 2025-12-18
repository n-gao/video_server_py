FROM python:3.12-slim

WORKDIR /app

# Install ffmpeg for video processing
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install uv for dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Copy application code
COPY app/ ./app/

# Create cache directory
RUN mkdir -p .cache

EXPOSE 5555

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "${VS_SERVER_HOST:-0.0.0.0}", "--port", "${VS_SERVER_PORT:-5555}"]
