# Base image with Python
FROM python:3.10-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    TZ=Asia/Kolkata

# Set work directory
WORKDIR /app

# Install FFmpeg and system dependencies
RUN apt-get update && \
    apt-get install -y ffmpeg gcc libffi-dev libssl-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy project files (including cookies.txt)
COPY . /app

# Install Python dependencies
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Command to run your bot
CMD ["python", "main.py"]
