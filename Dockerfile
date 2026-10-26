FROM python:3.12-slim-bookworm AS base

ARG APP_VERSION=dev
# Changes weekly in CI so that the pip layer (and with it yt-dlp) is rebuilt instead of served from cache.
ARG PIP_CACHE_BUST=0

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_VERSION=${APP_VERSION} \
    DATA_DIR=/data \
    HOME=/tmp \
    DENO_DIR=/tmp/deno \
    XDG_CACHE_HOME=/tmp/.cache

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg libopus0 tzdata \
 && rm -rf /var/lib/apt/lists/*

# yt-dlp needs a JavaScript runtime for YouTube (required since yt-dlp 2025.11.12).
COPY --from=denoland/deno:bin /deno /usr/local/bin/deno

WORKDIR /srv

COPY requirements.txt .
RUN echo "pip layer: ${PIP_CACHE_BUST}" && pip install -r requirements.txt

COPY app ./app
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

LABEL org.opencontainers.image.title="Melomancer" \
      org.opencontainers.image.description="Discord music bot with a web panel for tabletop RPG sessions" \
      org.opencontainers.image.version="${APP_VERSION}"

EXPOSE 8080
VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=4).status == 200 else 1)"

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app_factory", "--factory", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--forwarded-allow-ips", "*"]

# Test image: the same system packages and Python as production plus the test tools.
# `docker build --target test -t melomancer:test .` then
# `docker run --rm --entrypoint python melomancer:test -m pytest -p no:cacheprovider`
FROM base AS test
COPY requirements-dev.txt pytest.ini ./
RUN pip install -r requirements-dev.txt
COPY tests ./tests

# The last stage is what a plain `docker build .` produces.
FROM base AS release
