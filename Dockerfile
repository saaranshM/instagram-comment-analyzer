FROM python:3.13-slim

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy bundled GLiNER model (no HF download needed)
COPY models/ models/

# Copy application code
COPY *.py .

# Create output directory
RUN mkdir -p /app/output

ENTRYPOINT ["python", "fetch_comments.py"]
