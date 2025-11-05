FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for ML libraries
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    gfortran \
    libopenblas-dev \
    liblapack-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .

# Install base requirements first
RUN pip install --no-cache-dir flask numpy pandas scikit-learn redis requests prometheus-client gunicorn joblib

# Try to install optional ML libraries (fail gracefully if not available)
RUN pip install --no-cache-dir tensorflow==2.13.0 || echo "TensorFlow installation failed - LSTM models will be disabled"
RUN pip install --no-cache-dir prophet==1.1.4 || echo "Prophet installation failed - seasonal forecasting will be disabled"

# Copy application code
COPY app.py .

# Create non-root user
RUN useradd -m -u 1000 mluser && chown -R mluser:mluser /app
USER mluser

# Create model storage directory
RUN mkdir -p /tmp/models

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Start application
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "300", "--worker-class", "sync", "app:app"]