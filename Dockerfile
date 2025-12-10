# Lightweight Python base image
FROM python:3.11-slim

# Make logs show immediately and avoid pip cache
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Create and switch to app directory
WORKDIR /app

# Install dependencies first (better cache)
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your code
COPY . .

# Run your main file
CMD ["python", "main.py"]
