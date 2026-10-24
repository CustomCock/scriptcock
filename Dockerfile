# okm Script-Baukasten – Container-Image (Alternative zu systemd)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN useradd --system --create-home --home-dir /app baukasten
WORKDIR /app

COPY pyproject.toml ./
COPY app ./app
RUN pip install .

COPY blocks ./blocks
COPY recipes ./recipes
COPY katalog ./katalog
COPY registry ./registry
COPY static ./static

RUN mkdir -p /app/data && chown baukasten:baukasten /app/data
USER baukasten

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz')"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
