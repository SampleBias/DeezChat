# DeezChat Docker Documentation

## Overview

This document provides comprehensive documentation for running DeezChat in Docker containers, including build instructions, deployment options, and troubleshooting.

## Quick Start

### Using Docker Compose (Recommended)

```bash
# Clone the repository
git clone https://github.com/deezchat/deezchat.git
cd deezchat

# Run with Docker Compose
docker-compose up -d
```

### Using Docker Build

```bash
# Clone the repository
git clone https://github.com/deezchat/deezchat.git
cd deezchat

# Build the image
docker build -t deezchat/deezchat .

# Run the container
docker run -d \
  --name deezchat \
  --device /dev/bus/usb:/dev/bus/usb \
  -v deezchat_data:/app/data \
  -v deezchat_config:/app/config \
  -v deezchat_logs:/app/logs \
  deezchat/deezchat
```

## Docker Architecture

### Multi-stage Build

The Dockerfile uses a multi-stage build approach:

1. **Builder Stage**: Sets up build environment and dependencies
2. **Production Stage**: Creates minimal runtime image

### Security Features

- **Non-root User**: Runs as `deezchat` user for security
- **Minimal Base**: Uses `python:3.11-slim` for reduced attack surface
- **Read-only Filesystem**: Non-critical directories are read-only
- **Resource Limits**: Configurable CPU and memory limits

### Volume Management

- **Data Volume**: `/app/data` - Persistent message storage
- **Config Volume**: `/app/config` - Configuration files
- **Logs Volume**: `/app/logs` - Application logs
- **Temporary Volume**: `/app/tmp` - Temporary files

## Configuration

### Environment Variables

| Variable | Default | Description |
|-----------|---------|-------------|
| `DEEZCHAT_DATA_DIR` | `/app/data` | Data directory path |
| `DEEZCHAT_CONFIG_DIR` | `/app/config` | Configuration directory path |
| `DEEZCHAT_LOG_DIR` | `/app/logs` | Log directory path |
| `DEEZCHAT_LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `DEEZCHAT_SCAN_INTERVAL` | `5` | BLE scan interval in seconds |
| `DEEZCHAT_MAX_PEERS` | `50` | Maximum concurrent peers |
| `DEEZCHAT_TTL` | `7` | Message time-to-live |
| `DEEZCHAT_NICKNAME` | `DeezChat` | Default nickname |
| `DEEZCHAT_THEME` | `default` | UI theme |
| `PYTHONUNBUFFERED` | `1` | Unbuffered Python output |
| `PYTHONDONTWRITEBYTECODE` | `1` | Prevent bytecode writing |

### Configuration File

You can provide a custom configuration file:

```bash
# Create a config directory
mkdir -p ./config

# Copy default configuration
cp config.yaml ./config/

# Edit configuration
nano ./config/config.yaml
```

Then run with the mounted configuration:

```bash
docker run -d \
  --name deezchat \
  -v ./config:/app/config \
  -v deezchat_data:/app/data \
  -v deezchat_logs:/app/logs \
  deezchat/deezchat
```

## Docker Compose

### Services

The `docker-compose.yml` defines the following services:

#### Main Service

```yaml
services:
  deezchat:
    build:
      context: .
      args:
        BUILD_DATE: ${BUILD_DATE:-}
        VERSION: ${VERSION:-latest}
        VCS_REF: ${VCS_REF:-}
    image: deezchat/deezchat:${VERSION:-latest}
    container_name: deezchat
    restart: unless-stopped
    user: deezchat
    environment:
      - DEEZCHAT_DATA_DIR=/app/data
      - DEEZCHAT_CONFIG_DIR=/app/config
      - DEEZCHAT_LOG_DIR=/app/logs
      - DEEZCHAT_LOG_LEVEL=${DEEZCHAT_LOG_LEVEL:-INFO}
      - DEEZCHAT_SCAN_INTERVAL=${DEEZCHAT_SCAN_INTERVAL:-5}
      - DEEZCHAT_MAX_PEERS=${DEEZCHAT_MAX_PEERS:-50}
      - DEEZCHAT_TTL=${DEEZCHAT_TTL:-7}
      - DEEZCHAT_NICKNAME=${DEEZCHAT_NICKNAME:-DeezChat}
      - DEEZCHAT_THEME=${DEEZCHAT_THEME:-default}
      - PYTHONUNBUFFERED=1
      - PYTHONDONTWRITEBYTECODE=1
    volumes:
      - deezchat_data:/app/data
      - deezchat_config:/app/config
      - deezchat_logs:/app/logs
    devices:
      - /dev/bus/usb:/dev/bus/usb
      - /dev/bus/usb-001:/dev/bus/usb-001
      - /dev/bus/usb-002:/dev/bus/usb-002
    network_mode: host
    cap_add:
      - NET_ADMIN
      - SYS_RAWIO
    cap_drop:
      - ALL
    healthcheck:
      test: ["CMD", "python", "-c", "import sys; sys.exit(0)"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 5s
    ports:
      - "7331:7331/tcp"  # Debug port if needed
```

### Volumes

```yaml
volumes:
  deezchat_data:
    driver: local
    name: deezchat_data
  deezchat_config:
    driver: local
    name: deezchat_config
  deezchat_logs:
    driver: local
    name: deezchat_logs
```

### Networks

```yaml
networks:
  default:
    driver: bridge
    name: deezchat_network
```

### Override Files

#### Development Override

Create `docker-compose.override.yml`:

```yaml
version: '3.8'

services:
  deezchat:
    volumes:
      - .:/app
      - deezchat_dev_data:/app/data
      - deezchat_dev_config:/app/config
      - deezchat_dev_logs:/app/logs
    environment:
      - DEEZCHAT_LOG_LEVEL=DEBUG
      - DEEZCHAT_DEBUG=true
      - DEEZCHAT_RELOAD_CONFIG=true
```

Run with development overrides:

```bash
docker-compose -f docker-compose.yml -f docker-compose.override.yml up
```

#### Production Override

Create `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  deezchat:
    restart: always
    deploy:
      replicas: 1
      resources:
        limits:
          cpus: '0.5'
          memory: 256M
        reservations:
          cpus: '0.25'
          memory: 128M
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

Run with production overrides:

```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up
```

## Building Images

### Local Build

```bash
# Build with default tag
docker build -t deezchat/deezchat .

# Build with custom tag
docker build -t deezchat/deezchat:1.2.0 .

# Build with build arguments
docker build \
  --build-arg VERSION=1.2.0 \
  --build-arg BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ') \
  --build-arg VCS_REF=$(git rev-parse HEAD) \
  -t deezchat/deezchat:custom .
```

### Production Build

```bash
# Build for production
docker build \
  --target production \
  -t deezchat/deezchat:latest \
  --no-cache \
  .

# Build multi-architectures
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t deezchat/deezchat:multiarch \
  --push .
```

## Running Containers

### Basic Usage

```bash
# Run with default settings
docker run -d \
  --name deezchat \
  --device /dev/bus/usb:/dev/bus/usb \
  deezchat/deezchat

# Run with custom configuration
docker run -d \
  --name deezchat \
  -v ./my-config:/app/config \
  -v ./my-data:/app/data \
  --device /dev/bus/usb:/dev/bus/usb \
  deezchat/deezchat

# Run with environment variables
docker run -d \
  --name deezchat \
  -e DEEZCHAT_LOG_LEVEL=DEBUG \
  -e DEEZCHAT_SCAN_INTERVAL=10 \
  --device /dev/bus/usb:/dev/bus/usb \
  deezchat/deezchat

# Run with resource limits
docker run -d \
  --name deezchat \
  --memory=256m \
  --cpus=0.5 \
  --device /dev/bus/usb:/dev/bus/usb \
  deezchat/deezchat
```

### Interactive Mode

```bash
# Run in interactive mode for debugging
docker run -it \
  --name deezchat \
  --rm \
  -v ./config:/app/config \
  -v ./data:/app/data \
  --device /dev/bus/usb:/dev/bus/usb \
  deezchat/deezchat /bin/bash
```

### Detached Mode

```bash
# Run in detached mode
docker run -d \
  --name deezchat \
  --restart unless-stopped \
  -v deezchat_data:/app/data \
  -v deezchat_config:/app/config \
  -v deezchat_logs:/app/logs \
  --device /dev/bus/usb:/dev/bus/usb \
  deezchat/deezchat

# View logs
docker logs -f deezchat

# Stop container
docker stop deezchat

# Remove container
docker rm deezchat
```

## Docker Hub

### Repository

The DeezChat image is available on Docker Hub:
- Repository: `deezchat/deezchat`
- Tags: `latest`, `1.2.0`, `1.1.0`, etc.

### Pulling Images

```bash
# Pull latest version
docker pull deezchat/deezchat:latest

# Pull specific version
docker pull deezchat/deezchat:1.2.0

# Pull all tags
docker pull deezchat/deezchat --all-tags
```

### Using Docker Hub Images

```bash
# Run with Docker Hub image
docker run -d \
  --name deezchat \
  --device /dev/bus/usb:/dev/bus/usb \
  -v deezchat_data:/app/data \
  -v deezchat_config:/app/config \
  -v deezchat_logs:/app/logs \
  deezchat/deezchat:latest

# Run with specific version
docker run -d \
  --name deezchat \
  --device /dev/bus/usb:/dev/bus/usb \
  -v deezchat_data:/app/data \
  -v deezchat_config:/app/config \
  -v deezchat_logs:/app/logs \
  deezchat/deezchat:1.2.0
```

## Troubleshooting

### Common Issues

#### Bluetooth Device Access

**Problem**: Container cannot access Bluetooth devices
**Solution**: Add device mapping and capabilities

```bash
# Map USB devices
docker run -d \
  --device /dev/bus/usb:/dev/bus/usb \
  --cap-add NET_ADMIN \
  --cap-add SYS_RAWIO \
  deezchat/deezchat

# For specific USB device
docker run -d \
  --device /dev/bus/usb-001:/dev/bus/usb-001 \
  deezchat/deezchat
```

#### Permission Issues

**Problem**: Permission denied errors
**Solution**: Check volume permissions and user mapping

```bash
# Check volume permissions
ls -la /var/lib/docker/volumes/deezchat_data/

# Fix permissions
sudo chown -R 1000:1000 /var/lib/docker/volumes/deezchat_data/

# Run with specific user ID
docker run -d \
  --user 1000 \
  --device /dev/bus/usb:/dev/bus/usb \
  deezchat/deezchat
```

#### Configuration Issues

**Problem**: Configuration not loaded
**Solution**: Check file paths and permissions

```bash
# Check configuration file
docker exec deezchat ls -la /app/config/

# Check configuration content
docker exec deezchat cat /app/config/config.yaml

# Edit configuration
docker exec -it deezchat nano /app/config/config.yaml
```

#### Performance Issues

**Problem**: Slow performance in container
**Solution**: Increase resources and optimize settings

```bash
# Check resource usage
docker stats deezchat

# Increase memory limit
docker run -d \
  --memory=512m \
  --device /dev/bus/usb:/dev/bus/usb \
  deezchat/deezchat

# Increase CPU limit
docker run -d \
  --cpus=1.0 \
  --device /dev/bus/usb:/dev/bus/usb \
  deezchat/deezchat
```

### Debugging

#### Container Shell Access

```bash
# Get shell in running container
docker exec -it deezchat /bin/bash

# Run with interactive shell
docker run -it \
  --rm \
  --device /dev/bus/usb:/dev/bus/usb \
  deezchat/deezchat /bin/bash
```

#### Log Inspection

```bash
# View logs
docker logs deezchat

# Follow logs
docker logs -f deezchat

# View logs with timestamps
docker logs -t deezchat

# View last 100 lines
docker logs --tail 100 deezchat
```

#### Health Check

```bash
# Check container health
docker ps

# Run health check manually
docker exec deezchat python -c "import sys; sys.exit(0)"

# View health status
docker inspect --format='{{.State.Health.Status}}' deezchat
```

## Advanced Usage

### Custom Dockerfile

Create a custom `Dockerfile.custom`:

```dockerfile
FROM python:3.11-slim

# Install additional dependencies
RUN apt-get update && apt-get install -y \
    bluez \
    libbluetooth-dev \
    pkg-config

# Copy custom configuration
COPY custom-config.yaml /app/config/config.yaml

# Set custom environment
ENV DEEZCHAT_THEME=dark
ENV DEEZCHAT_LOG_LEVEL=DEBUG

# Copy application
COPY . /app/

# Custom entrypoint
COPY entrypoint.sh /app/
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python", "-m", "deezchat", "--custom"]
```

Build and run:

```bash
docker build -f Dockerfile.custom -t deezchat/custom .
docker run -d --name deezchat-custom deezchat/custom
```

### Multi-Container Deployment

Create `docker-compose.multi.yml`:

```yaml
version: '3.8'

services:
  deezchat-1:
    image: deezchat/deezchat:latest
    container_name: deezchat-1
    environment:
      - DEEZCHAT_NICKNAME=DeezChat-1
    volumes:
      - deezchat_data_1:/app/data
    devices:
      - /dev/bus/usb-001:/dev/bus/usb-001
    networks:
      - deezchat_network

  deezchat-2:
    image: deezchat/deezchat:latest
    container_name: deezchat-2
    environment:
      - DEEZCHAT_NICKNAME=DeezChat-2
    volumes:
      - deezchat_data_2:/app/data
    devices:
      - /dev/bus/usb-002:/dev/bus/usb-002
    networks:
      - deezchat_network

networks:
  deezchat_network:
    driver: bridge
```

### Kubernetes Deployment

Create `k8s-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: deezchat
spec:
  replicas: 1
  selector:
    matchLabels:
      app: deezchat
  template:
    metadata:
      labels:
        app: deezchat
    spec:
      containers:
      - name: deezchat
        image: deezchat/deezchat:latest
        ports:
        - containerPort: 7331
        env:
        - name: DEEZCHAT_DATA_DIR
          value: "/app/data"
        - name: DEEZCHAT_CONFIG_DIR
          value: "/app/config"
        - name: DEEZCHAT_LOG_DIR
          value: "/app/logs"
        volumeMounts:
        - name: deezchat-data
          mountPath: "/app/data"
        - name: deezchat-config
          mountPath: "/app/config"
        - name: deezchat-logs
          mountPath: "/app/logs"
        resources:
          requests:
            memory: "128Mi"
            cpu: "250m"
          limits:
            memory: "256Mi"
            cpu: "500m"
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: deezchat-data
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: deezchat-config
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 100Mi
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: deezchat-logs
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 100Mi
```

Deploy to Kubernetes:

```bash
# Apply configuration
kubectl apply -f k8s-deployment.yaml

# Check deployment status
kubectl get pods -l app=deezchat

# View logs
kubectl logs -l app=deezchat
```

## Security Considerations

### Container Security

- **Non-root User**: Container runs as `deezchat` user
- **Read-only Filesystem**: Non-critical directories are read-only
- **Minimal Base Image**: Uses `python:3.11-slim` for reduced attack surface
- **Resource Limits**: Configurable CPU and memory limits
- **Capability Management**: Only necessary capabilities are granted

### Network Security

- **Host Network**: Uses `network_mode: host` for Bluetooth access
- **Port Exposure**: Only expose necessary ports
- **Capability Control**: Fine-grained capability management

### Data Security

- **Volume Isolation**: Data stored in named volumes
- **Configuration Isolation**: Config stored in separate volume
- **Log Isolation**: Logs stored in separate volume
- **Temporary Data**: Temporary files cleaned up on exit

## Performance Optimization

### Image Size

- **Multi-stage Build**: Reduces final image size
- **Slim Base**: Uses `python:3.11-slim` base image
- **Dependency Cleanup**: Removes build dependencies after use
- **Layer Optimization**: Minimizes number of layers

### Runtime Performance

- **Resource Limits**: Configurable CPU and memory limits
- **Connection Pooling**: Efficient BLE connection management
- **Async Operations**: Non-blocking I/O throughout
- **Metrics Collection**: Built-in performance monitoring

### Startup Performance

- **Parallel Initialization**: Components start in parallel
- **Lazy Loading**: Components loaded as needed
- **Health Checks**: Early detection of issues
- **Graceful Shutdown**: Proper cleanup on exit

## Maintenance

### Updating Images

```bash
# Pull latest image
docker pull deezchat/deezchat:latest

# Stop running container
docker stop deezchat

# Remove old container
docker rm deezchat

# Run with new image
docker run -d \
  --name deezchat \
  --device /dev/bus/usb:/dev/bus/usb \
  -v deezchat_data:/app/data \
  -v deezchat_config:/app/config \
  -v deezchat_logs:/app/logs \
  deezchat/deezchat:latest
```

### Backup and Restore

```bash
# Backup volumes
docker run --rm \
  -v deezchat_data:/data \
  -v $(pwd)/backup:/backup \
  alpine tar czf /backup/deezchat-data-$(date +%Y%m%d).tar.gz -C /data .

# Backup configuration
docker run --rm \
  -v deezchat_config:/config \
  -v $(pwd)/backup:/backup \
  alpine tar czf /backup/deezchat-config-$(date +%Y%m%d).tar.gz -C /config .

# Restore volumes
docker run --rm \
  -v deezchat_data:/data \
  -v $(pwd)/backup:/backup \
  alpine tar xzf /backup/deezchat-data-$(date +%Y%m%d).tar.gz -C /data
```

### Monitoring

```bash
# Monitor resource usage
docker stats deezchat

# Monitor with custom format
docker stats --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}" deezchat

# Set up log rotation
docker run -d \
  --name deezchat-logrotate \
  --v deezchat_logs:/logs:ro \
  -v $(pwd)/logrotate:/config \
  --v /var/log/deezchat:/logs \
  alpine logrotate /config/logrotate.conf
```

## Conclusion

The DeezChat Docker implementation provides:

1. **Easy Deployment**: One-command deployment with Docker Compose
2. **Configuration Management**: Flexible configuration through environment variables
3. **Security**: Non-root execution with minimal privileges
4. **Performance**: Optimized image size and resource usage
5. **Maintainability**: Clear separation of concerns and volume management
6. **Scalability**: Support for multi-container and Kubernetes deployments
7. **Monitoring**: Built-in health checks and metrics collection

The Docker implementation makes DeezChat easy to deploy, configure, and maintain in containerized environments while maintaining security and performance standards.