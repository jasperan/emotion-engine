# EmotionSim Backend Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set environment variables (Oracle DB 26ai Free)
ENV PYTHONPATH=/app
ENV ORACLE_DB_HOST=oracle-db
ENV ORACLE_DB_PORT=1521
ENV ORACLE_DB_SERVICE=FREEPDB1
ENV ORACLE_DB_USER=emotionsim
ENV ORACLE_DB_PASSWORD=emotionsim

# Expose port
EXPOSE 8000

# Run the application
CMD ["python", "-m", "app.main"]
