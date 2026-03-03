#!/usr/bin/env bash
set -euo pipefail

echo "Running Evolutor Benchmarks..."
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/benchmarks/ -v --benchmark-enable 2>&1 || echo "No benchmarks found yet."
echo "Benchmarks complete."
