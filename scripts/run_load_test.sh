#!/bin/bash
# Run load test inside container

echo "Starting load test in ns_core container..."

docker exec ns_core python /app/scripts/load_test_24h.py