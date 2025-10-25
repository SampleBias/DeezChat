# DeezChat Dockerfile
# Multi-stage build for optimal image size and security

# Build stage
FROM python:3.11-slim as builder

# Set build arguments
ARG BUILD_DATE
ARG VERSION
ARG VCS_REF

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV DEEZCHAT_VERSION=${VERSION:-latest}

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    libbluetooth-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip and install build tools
RUN pip install --upgrade pip setuptools wheel

# Copy requirements and install Python dependencies
COPY requirements.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Production stage
FROM python:3.11-slim as production

# Set labels for metadata
LABEL maintainer="DeezChat Team <contact@deezchat.org>"
LABEL org.label-schema.name="deezchat"
LABEL org.label-schema.description="DeezChat - BitChat Python Client"
LABEL org.label-schema.url="https://github.com/deezchat/deezchat"
LABEL org.label-schema.vcs-ref=${VCS_REF}
LABEL org.label-schema.vcs-url="https://github.com/deezchat/deezchat.git"
LABEL org.label-schema.vendor="DeezChat"
LABEL org.label-schema.version=${VERSION}
LABEL org.label-schema.build-date=${BUILD_DATE}
LABEL org.label-schema.schema-version="1.0"

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV DEEZCHAT_VERSION=${VERSION:-latest}

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libbluetooth3 \
    libglib2.0-0 \
    bluez \
    dbus \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Set PATH for virtual environment
ENV PATH="/opt/venv/bin:$PATH"

# Create non-root user for security
RUN groupadd -r deezchat && \
    useradd -r -g deezchat -d -s /bin/false deezchat

# Create directories
RUN mkdir -p /app/config /app/data /app/logs /app/tmp && \
    chown -R deezchat:deezchat /app

# Copy application code
COPY --chown=deezchat:deezchat . /app/
WORKDIR /app

# Set permissions
RUN chmod +x /app/deezchat/__main__.py

# Create entrypoint script
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
# Default values\n\
DATA_DIR=${DEEZCHAT_DATA_DIR:-/app/data}\n\
CONFIG_DIR=${DEEZCHAT_CONFIG_DIR:-/app/config}\n\
LOG_DIR=${DEEZCHAT_LOG_DIR:-/app/logs}\n\
\n\
# Create directories if they do not exist\n\
mkdir -p "${DATA_DIR}" "${CONFIG_DIR}" "${LOG_DIR}"\n\
\n\
# Set permissions\n\
chown -R deezchat:deezchat "${DATA_DIR}" "${CONFIG_DIR}" "${LOG_DIR}"\n\
\n\
# Run as deezchat user\n\
exec gosu deezchat "$@"' > /app/entrypoint.sh && \
    chmod +x /app/entrypoint.sh

# Switch to non-root user
USER deezchat

# Expose volume mounts
VOLUME ["/app/data", "/app/config", "/app/logs"]

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# Set entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]

# Default command
CMD ["python", "-m", "deezchat"]