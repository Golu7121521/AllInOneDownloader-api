FROM python:3.11-slim

# Install system dependencies & FFmpeg (Required for video/audio merging)
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Expose port and run via gunicorn
EXPOSE 5000

# Timeout increased to 300s to allow large 4K/2K files to download and merge successfully
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "4", "--timeout", "300", "app:app"]
