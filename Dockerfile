FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

RUN python -m venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

RUN pip list --format=freeze

FROM python:3.11-slim AS runtime

LABEL maintainer="Anna Zaitseva"
LABEL version="1.0.0"
LABEL description="Dog Weight Tracker REST API"
LABEL build_date=${BUILD_DATE}
LABEL website="https://github.com/ClfrnAnna/DogWeightTracker"

RUN groupadd -r appuser && useradd -r -g appuser -s /bin/false appuser

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH"

COPY --chown=appuser:appuser api.py Dog.py DogRepository.py ./


RUN mkdir -p /app/data && \
    chown -R appuser:appuser /app && \
    chmod -R 755 /app

RUN ls -la /app

USER appuser

RUN whoami && id

EXPOSE 8000

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH="/app"

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import sys; import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health'); sys.exit(0)" || exit 1

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]