#!/bin/bash
# Quick deployment script for Case-to-Clearance

set -e

echo "=================================="
echo "Case-to-Clearance Deployment"
echo "=================================="
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found!"
    echo "Creating .env from template..."
    cp .env.example .env
    echo ""
    echo "❗ IMPORTANT: Edit .env with your Huawei Cloud credentials before continuing!"
    echo "   Required variables:"
    echo "   - MAAS_API_KEY"
    echo "   - OCR_AK"
    echo "   - OCR_SK"
    echo "   - OCR_PROJECT_ID"
    echo ""
    read -p "Press Enter after editing .env (or Ctrl+C to cancel)..."
fi

# Create production directories
echo "📁 Creating production directories..."
mkdir -p production/runs production/logs

# Build and start
echo "🐳 Building Docker image..."
docker-compose build

echo ""
echo "🚀 Starting application..."
docker-compose up -d

echo ""
echo "✅ Deployment complete!"
echo ""
echo "Application is running at:"
echo "  → http://localhost:8000"
echo ""
echo "To view logs:"
echo "  docker-compose logs -f"
echo ""
echo "To stop:"
echo "  docker-compose down"
echo ""
