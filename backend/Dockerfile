FROM python:3.12-slim

WORKDIR /app

# Install system dependencies including LibreOffice & fonts for vector rendering (EMF/WMF/VML)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libreoffice-draw-nogui \
    fonts-freefont-ttf \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and config
COPY . .

# Expose port
EXPOSE 8000

# Start command
CMD ["sh", "-c", "python scripts/create_default_admin.py && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
