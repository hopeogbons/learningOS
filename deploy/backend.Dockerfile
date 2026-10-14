FROM ghcr.io/astral-sh/uv:0.12.23@sha256:61d393e44e249f2e4b526b6c7ddcecce245946826e608e11c93ad4f5bba55b21 AS uv
FROM python:3.12.14-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy TIKTOKEN_CACHE_DIR=/app/backend/.tokenizer-cache
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN --mount=type=secret,id=cloud_ca,required=false \
    if [ -f /run/secrets/cloud_ca ]; then export SSL_CERT_FILE=/run/secrets/cloud_ca UV_SYSTEM_CERTS=true; fi; \
    uv sync --frozen --no-dev --no-install-project
COPY backend/ ./
RUN --mount=type=secret,id=cloud_ca,required=false \
    if [ -f /run/secrets/cloud_ca ]; then export SSL_CERT_FILE=/run/secrets/cloud_ca UV_SYSTEM_CERTS=true; fi; \
    uv sync --frozen --no-dev && uv run --frozen --no-dev python -m app.tokenizer_cache

FROM python:3.12.14-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e AS runtime
RUN --mount=type=secret,id=cloud_ca,required=false,mode=0444 \
    sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources; \
    if [ -f /run/secrets/cloud_ca ]; then printf 'Acquire::https::CaInfo "/run/secrets/cloud_ca";\n' > /etc/apt/apt.conf.d/99-build-trust; fi; \
    apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends ffmpeg=7:5.1.9-0+deb12u1 && \
    rm -f /etc/apt/apt.conf.d/99-build-trust && rm -rf /var/lib/apt/lists/*
RUN groupadd --gid 10001 learningos && useradd --uid 10001 --gid 10001 --no-create-home learningos && mkdir -p /data/private && chown -R learningos:learningos /data
WORKDIR /app/backend
COPY --from=build --chown=10001:10001 /app/backend /app/backend
COPY --chown=10001:10001 fixtures/ /app/fixtures/
COPY --chown=10001:10001 contracts/ /app/contracts/
ENV PATH="/app/backend/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PRIVATE_STORAGE_DIR=/data/private DATABASE_URL=sqlite:////data/learningos.db TIKTOKEN_CACHE_DIR=/app/backend/.tokenizer-cache
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/ready',timeout=4)" || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
