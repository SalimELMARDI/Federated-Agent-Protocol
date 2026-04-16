# Running FAP with Docker

This guide explains how to run the entire Federated Agent Protocol stack using Docker and Docker Compose.

## Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- 2GB free RAM
- 5GB free disk space

## Quick Start

### 1. Build the Docker images

```bash
cd fap
docker-compose build
```

This builds a multi-stage Docker image that installs dependencies and includes all FAP services.

### 2. Start the services

```bash
docker-compose up -d
```

This starts:
- **PostgreSQL** database on `localhost:5432`
- **Coordinator API** on `localhost:8011`
- **Participant Docs** on `localhost:8012`
- **Participant KB** on `localhost:8013`
- **Participant Logs** on `localhost:8014`

### 3. Verify services are running

```bash
docker-compose ps
```

Check service health:

```bash
curl http://localhost:8011/health
curl http://localhost:8012/health
curl http://localhost:8013/health
curl http://localhost:8014/health
```

### 4. Run the demo

```bash
docker-compose exec coordinator python examples/demo_scenario/run_demo.py \
  --coordinator-url http://coordinator:8000
```

Or directly from your host machine (requires Python 3.12 + local install):

```bash
cd fap
python -m pip install -e .
python examples/demo_scenario/run_demo.py --coordinator-url http://localhost:8011
```

### 5. Stop the services

```bash
docker-compose down
```

To also remove the database volume:

```bash
docker-compose down -v
```

## Development Workflow

### View logs

View logs for all services:
```bash
docker-compose logs -f
```

View logs for a specific service:
```bash
docker-compose logs -f coordinator
docker-compose logs -f participant-docs
```

### Connect to the database

```bash
docker-compose exec postgres psql -U fapuser -d fap_coordinator
```

### Access a service shell

```bash
docker-compose exec coordinator bash
docker-compose exec participant-docs bash
```

### Run tests in Docker

```bash
docker-compose run --rm coordinator python -m pytest
```

### Run type checking

```bash
docker-compose run --rm coordinator python -m mypy apps packages tests
```

### Run linting

```bash
docker-compose run --rm coordinator python -m ruff check .
```

## Environment Configuration

The docker-compose.yml uses sensible defaults. For customization:

1. Create a `.env` file in the `fap/` directory.

2. Edit `.env` with your values:
   ```
   POSTGRES_PASSWORD=your_secure_password
   DATABASE_URL=postgresql://fapuser:your_secure_password@postgres:5432/fap_coordinator
   ```

3. Services will automatically pick up the environment variables

## Architecture

```
┌─────────────────────────────────────┐
│      Docker Host Network            │
│  (fap-network bridge)               │
├─────────────────────────────────────┤
│                                     │
│  ┌───────────────────────────┐     │
│  │  Coordinator API (8011)   │     │
│  │  - FastAPI + uvicorn      │     │
│  │  - Alembic migrations     │     │
│  └───────────────────────────┘     │
│            │                        │
│  ┌─────────▼─────────┐             │
│  │  PostgreSQL (5432)│             │
│  │  - protocol_events│             │
│  │  - run_snapshots  │             │
│  └───────────────────┘             │
│            │                        │
│  ┌────────────────────────────┐   │
│  │  Participant Services      │   │
│  ├────────────────────────────┤   │
│  │ • Docs (8012)              │   │
│  │ • KB (8013)                │   │
│  │ • Logs (8014)              │   │
│  └────────────────────────────┘   │
│                                     │
└─────────────────────────────────────┘
```

## Networking

- Services communicate via the `fap-network` bridge
- Service names are resolvable hostnames (e.g., `coordinator`, `postgres`)
- External access via localhost ports (8011-8014)
- PostgreSQL accessible at `postgres:5432` from within containers

## Database Migrations

Migrations run automatically on coordinator startup via:

```bash
alembic upgrade head
```

To run migrations manually:

```bash
docker-compose run --rm coordinator alembic upgrade head
```

To create a new migration:

```bash
docker-compose run --rm coordinator alembic revision --autogenerate -m "description"
```

## Performance Tips

### 1. Use named volumes for persistence

The `postgres_data` volume persists the database between restarts.

### 2. Build once, run many times

Images are cached after first build. Rebuild only when dependencies change:

```bash
docker-compose build --no-cache
```

### 3. Use `.dockerignore`

The included `.dockerignore` excludes unnecessary files, reducing image size.

### 4. Limit resource usage (optional)

Edit `docker-compose.yml` to add resource limits:

```yaml
coordinator:
  deploy:
    resources:
      limits:
        cpus: '1'
        memory: 512M
```

## Troubleshooting

### Port already in use

If ports 8011-8014 or 5432 are already in use:

1. Find the process:
   ```bash
   lsof -i :8011
   ```

2. Either stop that process or change ports in `docker-compose.yml`:
   ```yaml
   ports:
     - "9011:8000"  # Maps container:8000 to host:9011
   ```

### Database connection failed

Ensure PostgreSQL is healthy:

```bash
docker-compose ps postgres
docker-compose logs postgres
```

Wait for the healthcheck to pass before running the demo.

### Import errors in container

Ensure the Python path is set correctly. It's configured in the Dockerfile:

```dockerfile
ENV PYTHONPATH=/app/apps/*/src:/app/packages/*/src
```

### Out of disk space

Clean up old images and containers:

```bash
docker system prune -a
```

## Production Considerations

This docker-compose setup is designed for **development and testing**. For production:

1. **Use environment-specific files**: Create `docker-compose.prod.yml`
2. **Secrets management**: Use Docker secrets or external secret managers (Vault, AWS Secrets Manager)
3. **Logging**: Configure centralized logging (ELK, CloudWatch, Datadog)
4. **Monitoring**: Add Prometheus + Grafana for metrics
5. **Orchestration**: Deploy to Kubernetes using Helm charts
6. **SSL/TLS**: Add reverse proxy (Nginx, Traefik) with certificates
7. **Database backups**: Implement automated PostgreSQL backups
8. **Multi-replica coordinator**: Use distributed database setup
9. **Rate limiting & auth**: Add authentication and rate limiting layers

## Kubernetes Deployment (Advanced)

To deploy FAP to Kubernetes:

1. Build and push images to a registry:
   ```bash
   docker build -t your-registry/fap:latest .
   docker push your-registry/fap:latest
   ```

2. Use Helm or Kustomize to create manifests based on `docker-compose.yml`

3. Deploy PostgreSQL as a StatefulSet with persistent storage

4. Deploy coordinator service as a Deployment with multiple replicas

5. Deploy participant services as Deployments

See [Kompose](https://kompose.io/) for automated docker-compose to Kubernetes conversion.

## See Also

- [Main README](./README.md)
- [Demo Scenario](./examples/demo_scenario/README.md)
- [Protocol Specification](./spec/README.md)
