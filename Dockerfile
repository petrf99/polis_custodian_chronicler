FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory inside the container
WORKDIR /app

# Copy requirements and install Python libraries
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Set entrypoint (main command)
CMD ["python", "bot.py"]
