# AGENTS.md

## Commands

- Run tests: `uv run pytest`
- Run tests with coverage: `uv run pytest --cov`
- Check lint: `uv run ruff check .`
- Check formatting: `uv run ruff format --check .`
- Apply lint fixes: `uv run ruff check . --fix`
- Apply formatting: `uv run ruff format .`
- Run type checking: `uv run pyright`

Before submitting changes, run:

```text
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest --cov
```

## Project Specification

- Adhere to SPEC.md

## Languages and Dependencies

- Python, type-annotated
- pytest (package name `pytest`) for testing
- `uv` for dependency management
- The OpenRouter agents SDK (package name `openrouter-agent-sdk`) for AI inference
    - Use this model: "nvidia/nemotron-3.5-lightning"
- The Finnhub API (package name `finnhub-python`) for everything concerning the stock market - checking if it's open or closed, getting stock prices, market news, etc.
    - Use the following endpoints:
        - "market status"
        - "market news"
        - "quote" - use current price
- Do not use any paid features in the APIs.

## Testing and Documentation

- Always write tests first, then implement.
    - Minimum coverage: 70%

- Document the reasoning behind technical decisions using comments.

## Credentials

- For local development, `FINNHUB_API_KEY` and `OPENROUTER_API_KEY` are stored in the project `.env`
- Use GitHub Actions Secrets for CI.
- Never commit, log, serialize, or store credentials in experiment data.
- Tests must use mocked API clients and must not require real credentials.
- Fail fast with a clear error when required credentials are missing.
