#!/usr/bin/env bash
set -euo pipefail

echo "Starting Evolutor Self-Improvement..."
evolutor evolve --generations 5 --target src/evolutor/
echo "Self-improvement complete."
