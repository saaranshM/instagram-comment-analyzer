FROM python:3.13-slim

WORKDIR /app

# Install system deps for torch/gliner
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the GLiNER model so it's baked into the image
RUN python -c "from gliner import GLiNER; GLiNER.from_pretrained('urchade/gliner_multi-v2.1')"

# Copy application code
COPY *.py .

# Create output directory
RUN mkdir -p /app/output

# Default entrypoint
ENTRYPOINT ["python", "fetch_comments.py"]
