# Use a slim Python image for performance and privacy
FROM python:3.9-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5002

# Create a non-root user for security (as requested in previous feedback)
RUN adduser --disabled-password --gecos "" webaudituser

# Set the working directory
WORKDIR /app

# Install system dependencies (lxml often needs libxml development headers)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libxml2-dev \
    libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Change ownership to the non-root user
RUN chown -R webaudituser:webaudituser /app

# Switch to the non-root user
USER webaudituser

# Expose the application port
EXPOSE 5002

# Run gunicorn to serve the app (optimized for crawler tasks)
CMD ["sh", "-c", "gunicorn app:app --bind 0.0.0.0:${PORT:-5002} --timeout 120 --workers 2"]
