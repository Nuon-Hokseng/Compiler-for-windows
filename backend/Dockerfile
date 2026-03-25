# Use the official Python image
FROM python:3.11-slim

# Install system dependencies required by Playwright/Chromium
RUN apt-get update && apt-get install -y \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium specifically
RUN playwright install chromium

# Copy the rest of the backend code
COPY . .

# Expose port (Render automatically uses the PORT env var)
EXPOSE 8000

# Command to run FastAPI via Xvfb for Playwright persistent contexts (listens on Render's dynamic PORT)
CMD ["sh", "-c", "xvfb-run -a uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
