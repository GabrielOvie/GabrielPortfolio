FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir docker httpx structlog

COPY sweeper.py .

CMD ["python", "sweeper.py"]
