# Use an official Python slim image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=5000

# Install system dependencies needed for OpenCV, FFmpeg, and video decoding
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Generate sample demo videos on build if not present
RUN python sample_generator.py

# Expose port
EXPOSE 5000

# Start server with python app.py — this is required, not optional: app.py's
# thread-startup code (camera workers, decision engine, PORT binding) lives
# inside `if __name__ == "__main__":`, which only runs when the script is
# executed directly. Running it via `gunicorn app:app` instead just imports
# the Flask object and NEVER starts the camera/detection threads, and also
# bypasses app.py's correct dynamic $PORT handling. Do not change this to
# gunicorn unless app.py's worker startup is first moved out of __main__.
CMD ["python", "app.py"]
