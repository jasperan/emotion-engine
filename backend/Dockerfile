# EmotionSim Backend Dockerfile
# Build context is the repo root so the emotionsim/ package and
# requirements.txt both live alongside this Dockerfile's inputs.
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml ./
COPY emotionsim ./emotionsim

ENV PYTHONPATH=/app
ENV ORACLE_DB_HOST=oracle-db
ENV ORACLE_DB_PORT=1521
ENV ORACLE_DB_SERVICE=FREEPDB1
ENV ORACLE_DB_USER=emotionsim
ENV ORACLE_DB_PASSWORD=emotionsim

EXPOSE 8000

CMD ["python", "-m", "emotionsim.main"]
