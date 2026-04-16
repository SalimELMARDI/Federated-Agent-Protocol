#!/bin/bash
# Setup script for Docker development

set -e

echo "🚀 FAP Docker Setup"
echo "==================="

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

echo "✅ Docker found: $(docker --version)"

# Check Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install it first."
    exit 1
fi

echo "✅ Docker Compose found: $(docker-compose --version)"

# Check if we're in the right directory
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ docker-compose.yml not found. Please run this script from the fap/ directory."
    exit 1
fi

echo ""
echo "📦 Building Docker images..."
echo "This may take a few minutes on first run..."
docker-compose build

echo ""
echo "✅ Build complete!"
echo ""
echo "📝 Next steps:"
echo "1. Start services:       docker-compose up -d"
echo "2. Check status:         docker-compose ps"
echo "3. View logs:            docker-compose logs -f"
echo "4. Run demo:             docker-compose exec coordinator python examples/demo_scenario/run_demo.py --coordinator-url http://localhost:8011"
echo "5. Stop services:        docker-compose down"
echo ""
echo "📚 For more info, see DOCKER.md"
