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

EXPOSE 8000

# Run the API server (model loads once at startup)
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
