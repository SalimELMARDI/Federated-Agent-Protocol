# Running FAP with Docker

This guide explains how to run the entire Federated Agent Protocol stack using Docker and Docker Compose.

## Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- 2GB free RAM
- 5GB free disk space

## Quick Start: The Minimal Path

```bash
cd fap

# 1. Build (one time)
docker-compose build

# 2. Start all services
docker-compose up -d

# 3. Wait for services to be healthy (check STATUS column)
docker-compose ps

# 4. Verify coordinator is ready
curl http://localhost:8011/health

# 5. Run the demo from inside the coordinator container
docker-compose exec coordinator python examples/demo_scenario/run_demo.py \
  --coordinator-url http://coordinator:8000

# Expected Demo Output:
# Task created: 202 Accepted ✓
# Orchestration completed: 200 OK ✓
# Participants executed:
#   - participant_docs ✓
#   - participant_kb ✓
#   - participant_logs ✓
# Results merged and persisted ✓
```

## Service URLs & Ports

| Service | Host Port | Container URL | Purpose |
|---------|-----------|---|---------|
| **Coordinator** | 8011 | `http://coordinator:8000` | Task orchestration & aggregation |
| **Participant Docs** | 8012 | `http://participant-docs:8000` | Document search |
| **Participant KB** | 8013 | `http://participant-kb:8000` | Knowledge base search |
| **Participant Logs** | 8014 | `http://participant-logs:8000` | Log search |
| **PostgreSQL** | 5432 | `postgres:5432` | Coordinator database |

**Access from your computer:** `http://localhost:PORT`  
**Access from inside containers:** `http://service-name:8000`

## Verification Steps

### 1. Check all services are healthy
```bash
docker-compose ps
```
All services should show `Up` with healthy status ✅

### 2. Test each health endpoint
```bash
# Coordinator health check
curl http://localhost:8011/health

# Participant health checks
curl http://localhost:8012/health
curl http://localhost:8013/health
curl http://localhost:8014/health

# All should return 200 OK with JSON response
```

### 3. Run the complete demo scenario
```bash
docker-compose exec coordinator python examples/demo_scenario/run_demo.py \
  --coordinator-url http://coordinator:8000
```

This tests:
- Task creation and acceptance
- Participant evaluation and execution  
- Policy attestation
- Aggregation and result computation
- Event persistence

### 4. View live logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f coordinator
docker-compose logs -f participant-docs
docker-compose logs -f participant-kb
docker-compose logs -f participant-logs
```

## Inspecting After the Demo

### View the run that was created
```bash
# Get the run_id from demo output, then:
curl http://localhost:8011/runs/{run_id}
```

### Inspect all protocol events
```bash
curl http://localhost:8011/runs/{run_id}/events
```

## Stopping Services

```bash
# Stop services (keeps database)
docker-compose down

# Stop and remove database volume (clean slate)
docker-compose down -v
```

## Development Workflows

### Running tests
```bash
docker-compose run --rm coordinator python -m pytest

# Or specific test file
docker-compose run --rm coordinator python -m pytest tests/test_coordinator_ask_api.py
```

### Type checking
```bash
docker-compose run --rm coordinator python -m mypy apps packages tests
```

### Linting
```bash
docker-compose run --rm coordinator python -m ruff check .
```

### Database shell
```bash
docker-compose exec postgres psql -U fapuser -d fap_coordinator
```

### Service shell
```bash
docker-compose exec coordinator bash
docker-compose exec participant-docs bash
```

### View database migrations
```bash
docker-compose exec coordinator alembic current
docker-compose exec coordinator alembic history
```

## Environment Configuration

The `docker-compose.yml` uses these environment variables. To customize:

1. Create `.env` file in `fap/` directory
2. Override any value:
   ```
   POSTGRES_PASSWORD=your_secure_password
   DATABASE_URL=postgresql://fapuser:your_secure_password@postgres:5432/fap_coordinator
   ```
3. Services automatically pick up `.env` values

## Architecture

```
Docker Network (fap-network)
│
├── PostgreSQL (5432)
│   ├── protocol_events table
│   └── run_snapshots table
│
├── Coordinator API (8000 → 8011)
│   ├── Reads env vars for participant URLs
│   ├── Runs alembic migrations on startup
│   └── Depends on postgres healthcheck
│
├── Participant Docs (8000 → 8012)
│   ├── Loads local data from examples/local_docs/data
│   └── Exports policy-governed results
│
├── Participant KB (8000 → 8013)
│   ├── Loads local data from examples/local_kb/data
│   └── Exports policy-governed results
│
└── Participant Logs (8000 → 8014)
    ├── Loads local data from examples/local_logs/data
    └── Exports policy-governed results
```

## Troubleshooting

### Port already in use
```bash
# Find process using port 8011
lsof -i :8011

# Or change ports in docker-compose.yml:
# ports:
#   - "9011:8000"  # Use 9011 instead
```

### Database migration failed
```bash
# Check logs
docker-compose logs coordinator

# Connect to DB and inspect
docker-compose exec postgres psql -U fapuser -d fap_coordinator
```

### Service not healthy
```bash
# View container logs
docker-compose logs {service-name}

# Check service details
docker-compose ps {service-name}

# Restart service
docker-compose restart {service-name}
```

### Clean rebuild
```bash
# Remove images and rebuild
docker-compose down
docker image rm fap-coordinator  # if named
docker-compose build --no-cache
docker-compose up -d
```

## Production Considerations

This docker-compose setup is **development-focused**. For production:

### Security
- Use secrets management (Docker Secrets, Vault, AWS Secrets Manager)
- Don't expose unnecessary ports
- Use SSL/TLS via reverse proxy (Nginx, Traefik)
- Implement network policies and firewalls

### Deployment
- Push images to private registry (Docker Hub, ECR, GCR)
- Use environment-specific compose files
- Implement ConfigMap/Secrets in Kubernetes
- Set resource limits and requests

### Operations
- Centralize logs (ELK, CloudWatch, Datadog)
- Set up monitoring (Prometheus + Grafana)
- Configure alerting
- Implement automated backups for PostgreSQL
- Use managed databases (RDS, Cloud SQL)

### Scaling
- For multi-node coordinator: use external PostgreSQL
- For Kubernetes: generate manifests from docker-compose via Kompose
- Add load balancer in front of participants if scaling

## See Also

- [Main README](./README.md)
- [Demo Scenario](./examples/demo_scenario/README.md)
- [Protocol Specification](./spec/README.md)
- [Commit Guidelines](./COMMIT_GUIDELINES.md)
