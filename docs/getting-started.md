# Getting Started

## Installation

```bash
git clone https://github.com/mariklolik/evolutor.git
cd evolutor
pip install -e ".[dev]"
```

## Quick Start

### Initialize a project
```bash
evolutor init .
```

### Submit a task
```bash
evolutor task "Add error handling to the API module"
```

### Run evolution
```bash
evolutor evolve --generations 10 --target src/
```

### Check status
```bash
evolutor status
```

### View history
```bash
evolutor history --count 20
```

### Interactive chat
```bash
evolutor chat
```

### Full-screen TUI
```bash
evolutor tui
```

## Docker Setup

```bash
docker-compose up -d
```

This starts:
- Evolutor service
- Redis (task queue)
- ChromaDB (vector memory)
- Sandbox container

## Configuration

Edit `configs/default.toml` or set environment variables:
- `ANTHROPIC_API_KEY` — API key for Claude
- `REDIS_URL` — Redis connection URL
- `EVOLUTOR_LOG_LEVEL` — Log level (DEBUG, INFO, WARNING, ERROR)
