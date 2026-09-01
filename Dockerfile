FROM python:3.11-slim
ARG KRONOS_REPO=https://github.com/shiyu-coder/Kronos.git
ARG KRONOS_COMMIT=67b630e67f6a18c9e9be918d9b4337c960db1e9a
RUN apt-get update && apt-get install -y --no-install-recommends git build-essential curl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml README.md /app/
COPY kcos /app/kcos
RUN pip install --no-cache-dir .
RUN git clone "${KRONOS_REPO}" /opt/Kronos \
    && cd /opt/Kronos \
    && git checkout "${KRONOS_COMMIT}" \
    && test "$(git rev-parse HEAD)" = "${KRONOS_COMMIT}" \
    && pip install --no-cache-dir -r requirements.txt
ENV PYTHONPATH=/opt/Kronos:/app
ENV KRONOS_UPSTREAM_PATH=/opt/Kronos
ENV KCOS_RUNTIME_DIR=/app/runtime
COPY config /app/config
COPY db /app/db
COPY scripts /app/scripts
RUN mkdir -p /app/runtime /app/artifacts
HEALTHCHECK --interval=15s --timeout=5s --retries=4 CMD curl -fsS http://localhost:8080/health || exit 1
CMD ["python", "-m", "kcos.main", "runtime"]
