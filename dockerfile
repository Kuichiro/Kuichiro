FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /storage/emulated/0/Download/Logs/ Generated_Results database temp backups

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Start the bot
CMD ["python", "bot.py"]