FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

COPY pyproject.toml ./
COPY uv.lock ./
COPY src ./src
COPY docs ./docs
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

RUN uv sync --locked --no-dev \
    && mkdir -p /tmp/ytdlp_bot_downloads \
    && chown -R appuser:appuser /app /tmp/ytdlp_bot_downloads \
    && chmod +x /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["/app/.venv/bin/python", "-m", "ytdlp_bot.main"]
