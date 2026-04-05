@echo off
REM Setup script for Docker development on Windows

setlocal enabledelayedexpansion

echo 🚀 FAP Docker Setup
echo ===================

REM Check Docker
docker --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker is not installed. Please install Docker Desktop first.
    exit /b 1
)

for /f "tokens=*" %%i in ('docker --version') do set DOCKER_VERSION=%%i
echo ✅ Docker found: %DOCKER_VERSION%

REM Check Docker Compose
docker-compose --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker Compose is not installed. Please install Docker Desktop first.
    exit /b 1
)

for /f "tokens=*" %%i in ('docker-compose --version') do set COMPOSE_VERSION=%%i
echo ✅ Docker Compose found: %COMPOSE_VERSION%

REM Check if we're in the right directory
if not exist "docker-compose.yml" (
    echo ❌ docker-compose.yml not found. Please run this script from the fap\ directory.
    exit /b 1
)

echo.
echo 📦 Building Docker images...
echo This may take a few minutes on first run...
docker-compose build

echo.
echo ✅ Build complete!
echo.
echo 📝 Next steps:
echo 1. Start services:       docker-compose up -d
echo 2. Check status:         docker-compose ps
echo 3. View logs:            docker-compose logs -f
echo 4. Run demo:             docker-compose exec coordinator python examples/demo_scenario/run_demo.py --coordinator-url http://localhost:8011
echo 5. Stop services:        docker-compose down
echo.
echo 📚 For more info, see DOCKER.md
