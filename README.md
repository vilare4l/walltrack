# WallTrack

Intelligent wallet tracking and automated trading system for Solana memecoins.

## Overview

WallTrack monitors profitable Solana wallets, analyzes their trading patterns, and executes copy-trades with configurable risk management and exit strategies.

## Features

- **Wallet Intelligence**: Discover and profile high-performing wallets
- **Cluster Analysis**: Detect coordinated trading patterns via Neo4j graph
- **Real-Time Signals**: Process Helius webhooks with multi-factor scoring
- **Automated Trading**: Execute via Jupiter with dynamic position sizing
- **Risk Management**: Circuit breakers, position limits, capital protection
- **Operator Dashboard**: Gradio UI for configuration and monitoring

## Tech Stack

- **Runtime**: Python 3.11+, AsyncIO
- **API**: FastAPI + Uvicorn
- **UI**: Gradio
- **Databases**: Neo4j (graph), Supabase (PostgreSQL + Vectors)
- **External APIs**: Helius, Jupiter, DexScreener

## Quick Start

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest

# Start the application
uv run walltrack
```

## Development

```bash
# Install with dev dependencies
uv sync --extra test --extra dev

# Run tests with coverage
uv run pytest --cov=walltrack

# Type checking
uv run mypy src/walltrack --strict

# Linting
uv run ruff check src/
```

## Documentation

- [Architecture](docs/architecture.md)
- [PRD](docs/prd.md)
- [Testing Guide](docs/TESTING.md)

## License

MIT
