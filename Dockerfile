# Use the official Python 3.11 image as base.
FROM python:3.11-slim

# Set working directory.
WORKDIR /app

# Runtime environment.
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV PYTHONIOENCODING=utf-8

# Install system dependencies.
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code.
COPY . .

# Create data directories.
RUN mkdir -p /app/data/logs

# Set script permissions.
RUN chmod +x start.sh

# Start command.
CMD ["./start.sh"] 
