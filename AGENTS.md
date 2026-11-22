# AGENTS.md

## Project Specification

- Adhere to SPEC.md

## Languages and Dependencies

- Python, type-annotated
- pytest (package name `pytest`) for testing
- `uv` for dependency management
- The OpenRouter agents SDK (package name `openrouter-agent-sdk`) for AI inference
	- Only use free models and features (e.g. no web search)
- The Finnhub API (package name `finnhub-python`) for everything concerning the stock market - checking if it's open or closed, getting stock prices, market news, etc.

## Testing and Documentation

- Always write tests first, then implement.
- Document the reasoning behind technical decisions.