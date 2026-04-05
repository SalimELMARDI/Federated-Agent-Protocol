# GitHub Actions CI/CD Workflows

This directory contains GitHub Actions workflows for automated testing and deployment.

## Workflows

### 1. `docker-test.yml` — Docker Build & Test Suite

**Triggers:**
- Push to `main` or `develop` branches
- Pull requests targeting `main` or `develop`
- Manual workflow dispatch

**Jobs:**

#### `build-and-test`
- Builds Docker images from Dockerfile
- Starts the complete docker-compose stack
- Waits for all services to be healthy (health checks pass)
- Verifies docker-compose configuration is valid
- Runs API health endpoint tests
- Executes the FAP demo scenario
- Runs full pytest test suite
- Runs mypy type checking
- Runs ruff linting
- Collects and uploads logs on failure
- Cleans up all containers and volumes

**Key Features:**
- 30-minute timeout for slow builds
- Waits up to 60 seconds for services to stabilize
- Comprehensive logging on failure
- Auto-cleanup (always runs)

#### `lint-dockerfile`
- Uses hadolint to lint the Dockerfile
- Checks for best practices and potential issues
- Non-blocking (continues on errors)

#### `security-scan`
- Uses Trivy to scan for vulnerabilities
- Generates SARIF report
- Uploads to GitHub Security tab
- Non-blocking

#### `build-and-push-image`
- Only runs after successful tests
- Only on `main` and `develop` branches (not PRs)
- Builds optimized Docker image using buildx
- Pushes to GitHub Container Registry (ghcr.io)
- Uses semantic versioning tags
- Caches layers for faster rebuilds

### 2. `docker-compose-validate.yml` — Configuration Validation

**Triggers:**
- Changes to docker-compose.yml
- Changes to Dockerfile or .dockerignore
- Changes to entrypoint scripts
- Changes to this workflow itself

**Jobs:**

#### `validate`
- Validates docker-compose YAML syntax
- Checks all required services are defined
- Verifies volume definitions
- Checks network configuration
- Validates environment variables placement
- Ensures participant URLs use container ports (8000)
- Validates shell script syntax

#### `docker-compose-rules`
- Checks for health checks on services
- Verifies best practices
- Checks dependency management
- Validates Dockerfile optimization

## What Gets Tested

✅ **Docker Images**
- Builds successfully
- Contains all dependencies
- Multi-stage build optimization

✅ **docker-compose.yml**
- Valid YAML syntax
- Services correctly defined
- Volume and network setup correct
- Environment variables properly placed
- Participant URLs use internal network

✅ **Service Health**
- All services start within 60 seconds
- Health check endpoints respond 200 OK
- Database is ready before coordinator
- Services can communicate

✅ **Functionality**
- Demo scenario completes successfully
- All pytest tests pass
- Type checking passes
- Code linting passes

✅ **Configuration**
- Shell scripts have valid syntax
- Best practices are followed
- No obvious issues detected

## Usage

### Local Testing (Before Push)

```bash
cd fap

# Run locally what CI will run
docker-compose build
docker-compose up -d

# Wait for services
sleep 10

# Check health
curl http://localhost:8011/health

# Run demo
docker-compose exec coordinator python examples/demo_scenario/run_demo.py \
  --coordinator-url http://localhost:8011

# Run tests
docker-compose run --rm coordinator python -m pytest

# Cleanup
docker-compose down -v
```

### Viewing CI Results

- **Push to branch:** View in Actions tab
- **Pull Request:** See checks on PR page
- **Image Registry:** ghcr.io/{owner}/federated-agent-protocol

### Fixing CI Failures

Common issues and solutions:

**❌ Service failed to become healthy**
- Check logs: `docker-compose logs {service}`
- Verify health endpoints exist
- Increase timeout in workflow

**❌ Docker build fails**
- Check Dockerfile syntax
- Verify base image is accessible
- Check for large files in build context

**❌ Tests fail in CI but pass locally**
- Check docker-compose config is valid
- Verify environment variables
- Check for timing issues (increase sleep)

**❌ Type checking fails**
- Run `docker-compose run --rm coordinator python -m mypy apps packages tests`
- Fix type hints locally first

**❌ Linting fails**
- Run `docker-compose run --rm coordinator python -m ruff check .`
- Fix issues or add to ruff config

## Customization

### Adding New Tests

Edit `docker-test.yml` to add new test steps:

```yaml
- name: Run my custom test
  run: |
    cd fap
    docker-compose exec -T coordinator python -m pytest tests/my_test.py -v
```

### Changing Docker Registry

Edit `docker-compose-validate.yml` to push to different registry:

```yaml
- name: Log in to Docker Hub
  with:
    username: ${{ secrets.DOCKER_USERNAME }}
    password: ${{ secrets.DOCKER_PASSWORD }}
    registry: docker.io
```

### Adding Scheduled Builds

Add to workflow trigger:

```yaml
on:
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM UTC
```

## Environment Secrets

None required for public repositories. For private:

- `GITHUB_TOKEN` — Automatically provided
- `DOCKER_USERNAME` — Optional for custom registry
- `DOCKER_PASSWORD` — Optional for custom registry

## Monitoring & Alerts

- **GitHub Actions tab:** Real-time status
- **Branch protection rules:** Block merges if tests fail
- **Security tab:** Trivy vulnerability alerts
- **Container registry:** ghcr.io for built images

## Performance

- **Build time:** ~2-3 minutes (first run), ~30-60 seconds (cached)
- **Test time:** ~5-10 minutes total
- **Total workflow:** ~15-20 minutes

## Cost

- **GitHub Actions:** Free for public repos (unlimited)
- **Container Registry:** Free tier available
- **Cost for private repos:** ~$0-20/month for typical usage

## Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [docker-compose CLI Reference](https://docs.docker.com/compose/reference/)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
