# Contributing to hive

## Development Setup

```bash
git clone https://github.com/sabre-ai/hive.git
cd hive

# Python backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

## Running Tests

```bash
pytest tests/ -v
```

Run a single test file or test:

```bash
pytest tests/test_store.py -v
pytest tests/test_store.py::test_function_name -v
```

## Linting and Formatting

```bash
ruff check src/ tests/          # lint
ruff format src/ tests/          # format
ruff format --check src/ tests/  # check format without changing
```

## Submitting Changes

1. Fork the repo and create a branch from `main`
2. Make your changes
3. Add tests for new functionality
4. Ensure `pytest`, `ruff check`, and `ruff format --check` all pass
5. Open a pull request

## Contribution Types

=== "Enricher"

    Enrichers attach context to sessions at capture time. See the
    [Enrichers reference](reference/enrichers.md) for a full guide.

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

=== "Capture Adapter"

    Capture adapters ingest sessions from different AI tools. Implement the
    `CaptureAdapter` protocol in `src/hive/capture/base.py`.

    See `src/hive/capture/claude_code.py` for the reference implementation.

=== "Bug Fix"

    1. Check existing issues or open a new one describing the bug
    2. Write a failing test that reproduces the issue
    3. Fix the bug and verify the test passes
    4. Submit a PR referencing the issue number

=== "Documentation"

    Documentation lives in `docs/` and uses MkDocs Material.

    ```bash
    pip install mkdocs-material
    mkdocs serve  # preview at http://localhost:8000
    ```

    Keep docs example-first and concrete. Every code block should be runnable.

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

- Python 3.11+ with type hints
- Formatted with `ruff format`
- Linted with `ruff check` (rules: E, F, I, UP, B, SIM)
- Line length: 100
- Double quotes
- No unnecessary abstractions -- keep it simple
