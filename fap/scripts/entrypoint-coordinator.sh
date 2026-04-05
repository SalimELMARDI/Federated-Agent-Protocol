#!/bin/bash
# Coordinator entrypoint script

set -e

echo "🚀 FAP Coordinator Starting..."
echo "  Database: $DATABASE_URL"
echo "  Docs participant: ${PARTICIPANT_DOCS_EVALUATE_URL:-http://participant-docs:8000/evaluate}"
echo "  KB participant: ${PARTICIPANT_KB_EVALUATE_URL:-http://participant-kb:8000/evaluate}"
echo "  Logs participant: ${PARTICIPANT_LOGS_EVALUATE_URL:-http://participant-logs:8000/evaluate}"

# Wait for database to be ready (max 30 seconds)
echo "⏳ Waiting for PostgreSQL to be ready..."
max_attempts=30
attempt=0
while [ $attempt -lt $max_attempts ]; do
  if python -c "import psycopg; psycopg.connect('$DATABASE_URL')" 2>/dev/null; then
    echo "✅ Database is ready"
    break
  fi
  attempt=$((attempt + 1))
  if [ $attempt -eq $max_attempts ]; then
    echo "⚠️  Database not ready after 30 seconds, continuing anyway..."
  else
    echo "  Attempt $attempt/$max_attempts..."
    sleep 1
  fi
done

# Run database migrations (non-blocking)
if command -v python &> /dev/null; then
  echo "📦 Attempting database migrations..."
  if python -m alembic upgrade head 2>&1 | grep -q "error\|failed"; then
    echo "⚠️  Migrations had warnings, but continuing..."
  else
    echo "✅ Database migrations completed"
  fi || true
fi

# Start coordinator
echo "🌐 Starting FastAPI server on 0.0.0.0:8000..."
exec python -m uvicorn coordinator_api.app:app --host 0.0.0.0 --port 8000
