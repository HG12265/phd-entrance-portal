FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
# - build-essential: for pymysql/bcrypt compilation
# - imagemagick: EMF/WMF/vector image conversion (primary tool for Wand)
# - ghostscript: required by ImageMagick for PDF/PS handling (improves EMF support)
# - libmagickwand-dev: development headers required by Wand Python bindings
# Note: python:3.12-slim uses Debian Trixie (13) — libmagickcore-6.q16-6-extra not available there
# imagemagick pulls in the required codec libs automatically on Trixie
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    imagemagick \
    ghostscript \
    libmagickwand-dev \
    && rm -rf /var/lib/apt/lists/*

# Patch ImageMagick policy.xml to allow reading EMF, WMF, and other formats
# Default Debian policy restricts many formats for security — we selectively allow required ones
RUN POLICY_FILE=$(find /etc/ImageMagick-* -name policy.xml 2>/dev/null | head -1) && \
    if [ -n "$POLICY_FILE" ]; then \
        sed -i 's/rights="none" pattern="EMF"/rights="read|write" pattern="EMF"/g' "$POLICY_FILE" 2>/dev/null || true; \
        sed -i 's/rights="none" pattern="WMF"/rights="read|write" pattern="WMF"/g' "$POLICY_FILE" 2>/dev/null || true; \
        sed -i 's/rights="none" pattern="MSL"/rights="read|write" pattern="MSL"/g' "$POLICY_FILE" 2>/dev/null || true; \
        sed -i 's/<policy domain="coder" rights="none" pattern="PDF"/<policy domain="coder" rights="read|write" pattern="PDF"/g' "$POLICY_FILE" 2>/dev/null || true; \
        echo "ImageMagick policy patched: $POLICY_FILE"; \
    else \
        echo "No ImageMagick policy.xml found (may use defaults)"; \
    fi

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and config
COPY . .

# Ensure uploads directories exist
RUN mkdir -p uploads/candidate_photos uploads/candidate_excels \
    uploads/question_excels uploads/question_images \
    uploads/question_images/original

# Expose port
EXPOSE 8000

# Start command (production: gunicorn; dev: uvicorn)
CMD ["sh", "-c", "python scripts/create_default_admin.py && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
