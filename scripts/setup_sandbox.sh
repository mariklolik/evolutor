#!/usr/bin/env bash
set -euo pipefail

echo "Setting up Evolutor Sandbox..."

# Create sandbox directories
mkdir -p /tmp/evolutor/worktrees
mkdir -p /tmp/evolutor/sandbox

# Pull base image
docker pull python:3.11-slim 2>/dev/null || echo "Docker not available, skipping image pull."

echo "Sandbox setup complete."
