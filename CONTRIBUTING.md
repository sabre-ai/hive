# Contributing to hive

## Development Setup

```bash
git clone https://github.com/sabre-ai/hive.git
cd hive

# Python backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"  # package is hive-team on PyPI

# Install pre-commit hooks
pre-commit install
```

## Running Tests

```bash
pytest tests/ -v
```

## Linting and Formatting

```bash
ruff check src/ tests/       # lint
ruff format src/ tests/       # format
ruff format --check src/ tests/  # check format without changing
```

## Submitting Changes

1. Fork the repo and create a branch from `main`
2. Make your changes
3. Add tests for new functionality
4. Ensure `pytest`, `ruff check`, and `ruff format --check` all pass
5. Open a pull request

## Writing a Custom Enricher

Enrichers attach context to sessions at capture time. See [docs/enrichers.md](docs/enrichers.md) for a full guide.

Quick version:

```python
from hive.enrich.base import Enricher

class MyEnricher(Enricher):
    def name(self) -> str:
        return "my_enricher"

    def should_run(self, session: dict) -> bool:
        return True

    def run(self, session: dict) -> dict[str, Any]:
        return {"my_key": "computed_value"}
```

Register it in `src/hive/enrich/__init__.py`:

```python
ALL_ENRICHERS.append(MyEnricher())
```

No schema changes needed.

## Writing a Capture Adapter

Capture adapters ingest sessions from different AI tools. See [docs/adapters.md](docs/adapters.md) for a full guide.

## Project Structure

```
src/hive/
├── cli.py               # CLI commands (Click)
├── config.py            # Configuration
├── privacy.py           # Secret scrubbing
├── mcp_server.py        # MCP server (Claude interface)
├── capture/             # Capture adapters
├── enrich/              # Enrichers
├── store/               # SQLite storage + query API
└── serve/               # FastAPI REST API
```

## Code Style

- Python 3.10+ with type hints
- Formatted with `ruff format`
- Linted with `ruff check`
- No unnecessary abstractions — keep it simple
