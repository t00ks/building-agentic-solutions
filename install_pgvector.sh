#!/bin/bash

set -e

CONTAINER_NAME="$1"

if [ -z "$CONTAINER_NAME" ]; then
    echo "Usage: $0 <container-name>"
    exit 1
fi

echo "Installing pgvector in container '$CONTAINER_NAME'..."

PG_MAJOR=$(docker exec "$CONTAINER_NAME" psql -U postgres -tAc "SHOW server_version;" | cut -d'.' -f1)
if [ -z "$PG_MAJOR" ]; then
    echo "Failed to detect PostgreSQL version in container '$CONTAINER_NAME'."
    exit 1
fi

echo "Detected PostgreSQL major version: $PG_MAJOR"

echo "Installing dependencies..."
docker exec -u root "$CONTAINER_NAME" bash -c "\
    apt-get update && \
    apt-get install -y postgresql-server-dev-$PG_MAJOR postgresql-$PG_MAJOR-pgvector"

echo "Done. Remember to *enable* the extension ;)"