# Docker Deployment Guide

This guide covers deploying the Case-to-Clearance application using Docker and Docker Compose.

## Prerequisites

- Docker 20.10 or higher
- Docker Compose 2.0 or higher
- Huawei Cloud credentials (MaaS API key, OCR AK/SK)

## Quick Start

### 1. Configure Environment Variables

Create a `.env` file in the project root:

```bash
cp .env.example .env
# Edit .env with your Huawei Cloud credentials
```

For production, prefer injecting secrets via your platform (Docker secrets, CI/CD vaults, or managed secret stores) and keep `.env` out of source control.

### 2. Start the Application

```bash
# Build and start the application
docker-compose up -d

# View logs
docker-compose logs -f app

# Stop the application
docker-compose down
```

The application will be available at http://localhost:8000

## Deployment Options

### Option 1: Direct Docker Compose (Simple)

```bash
docker-compose up -d
```

This runs the application directly on port 8000.

### Option 2: With Nginx Reverse Proxy (Production)

```bash
# Start with nginx reverse proxy
docker-compose --profile with-nginx up -d
```

This runs:
- Application on port 8000 (internal only)
- Nginx on ports 80/443 (public-facing)

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MAAS_API_KEY` | Huawei Cloud MaaS API key | Required |
| `MAAS_REGION` | Huawei Cloud region | ap-southeast-1 |
| `MAAS_ENDPOINT` | MaaS API endpoint | https://api-ap-southeast-1... |
| `MAAS_MODEL_REASONER` | LLM for reasoning | deepseek-v3.1 |
| `MAAS_MODEL_WRITER` | LLM for generation | qwen3-32b |
| `OCR_ENDPOINT` | OCR API endpoint | https://ocr.ap-southeast-1... |
| `OCR_REGION` | OCR region | ap-southeast-1 |
| `OCR_AK` | OCR Access Key | Required |
| `OCR_SK` | OCR Secret Key | Required |
| `OCR_PROJECT_ID` | Huawei Cloud project ID | Required |
| `APP_ENV` | Environment | production |
| `APP_LOG_LEVEL` | Log level | INFO |
| `APP_MAX_UPLOAD_SIZE_MB` | Max file upload size | 20 |
| `MAX_REQUESTS_PER_MINUTE` | Rate limit | 60 |

## Volumes

The following volumes are persisted:

- `./production/runs` - Case data storage
- `./production/logs` - Application logs

## Health Checks

The application includes a health check endpoint:

```bash
curl http://localhost:8000/health
```

Docker Compose monitors this endpoint and will restart the container if it fails.

## Production Considerations

### 1. SSL/TLS Configuration

For production use with Nginx:

1. Obtain SSL certificates (Let's Encrypt recommended)
2. Place certificates in `./ssl/` directory:
   - `cert.pem` - SSL certificate
   - `key.pem` - Private key
3. Uncomment the HTTPS server block in `nginx.conf`

### 2. Resource Limits

Add resource limits to `docker-compose.yml`:

```yaml
services:
  app:
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M
```

### 3. Auto-restart Policy

The container is configured with `restart: unless-stopped`, which means:
- Automatic restart on failure
- Automatic restart on system reboot
- Manual stop required to disable

### 4. Logging

Logs are written to `./production/logs/`. To view logs:

```bash
# View all logs
docker-compose logs app

# Follow logs in real-time
docker-compose logs -f app

# View last 100 lines
docker-compose logs --tail=100 app
```

### 5. Backups

Back up the persisted volumes regularly:

```bash
# Backup case data
tar -czf backup-$(date +%Y%m%d).tar.gz production/runs/

# Backup to remote location
rsync -avz production/runs/ user@backup-server:/backups/case-to-clearance/
```

## Troubleshooting

### Container won't start

```bash
# Check logs
docker-compose logs app

# Check container status
docker-compose ps
```

### Permission issues

```bash
# Fix volume permissions
sudo chown -R $USER:$USER production/
```

### Port already in use

```bash
# Check what's using port 8000
lsof -i :8000

# Change port in docker-compose.yml
ports:
  - "8888:8000"  # Use 8888 instead
```

### OCR not working

1. Verify credentials in `.env` are correct
2. Check logs for OCR-related errors
3. Ensure OCR service is enabled in Huawei Cloud Console

### Memory issues

```bash
# Check container resource usage
docker stats

# Increase memory limit
# In docker-compose.yml, add:
services:
  app:
    mem_limit: 2g
```

## Scaling

For higher traffic, you can scale the application:

```bash
# Scale to 3 instances (requires load balancer)
docker-compose up -d --scale app=3
```

Note: Scaling requires a load balancer or nginx configuration for proper request distribution.

## Updating the Application

```bash
# Pull latest changes
git pull

# Rebuild and restart
docker-compose up -d --build

# Remove old images
docker image prune -a
```

## Development with Docker

For development, use the development override:

```bash
# Create docker-compose.override.yml for development
cat > docker-compose.override.yml << 'EOF'
services:
  app:
    volumes:
      - ./app:/app/app
      - ./samples:/app/samples
    environment:
      - APP_ENV=development
      - APP_LOG_LEVEL=DEBUG
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
EOF

# Start with development overrides
docker-compose up
```
